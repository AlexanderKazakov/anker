# OAuth 2.1 for MCP servers: a complete guide from zero to deployment

**If you're building an MCP server on AWS and the auth layer feels like a wall of acronyms, this guide is for you.** It takes you from "what is OAuth?" to understanding every HTTP request in the full MCP authentication flow — using a concrete example throughout: **Ankify**, a Lambda-based MCP server behind CloudFront that generates Anki flashcard decks, authenticated via FastMCP's `AWSCognitoProvider` and AWS Cognito. Every concept builds on the last, so read in order.

---

## Part 1: Why OAuth exists (and why passwords and API keys won't cut it)

Imagine you build Ankify and deploy it as an MCP server. Users connect via Claude Desktop (or Cursor, or any MCP client) and say "make me flashcards about mitochondria." The server calls your tool, generates a deck, and returns it. Simple — until you want to know *who* is asking, enforce usage limits, or protect the endpoint from unauthorized access.

Your first instinct might be: "I'll give each user an API key." This works for simple APIs, but it has serious problems in the MCP world. **API keys are shared secrets** — the user gives the key to Claude Desktop, which sends it to your server. If Claude Desktop is compromised, or the key leaks in logs, or the user copy-pastes it into a second tool, that key grants full access with no way to limit scope, expire it gracefully, or revoke it without disrupting the user. Worse, if you ask users for their *password* to authenticate, you're training them to type credentials into third-party apps — a security anti-pattern.

**OAuth solves this with a simple principle: delegation without credential sharing.** The classic analogy is the valet key. Your car's valet key lets the parking attendant drive but not open the trunk or glove box. You're granting *limited, revocable access* without handing over your full set of keys. In OAuth terms, you (the **Resource Owner**) give Claude Desktop (the **Client**) a limited-scope token to access Ankify (the **Resource Server**), issued by a trusted authority — Cognito (the **Authorization Server**) — and you never type your password into Claude Desktop itself.

### The four roles in every OAuth interaction

Every OAuth flow involves exactly four roles. Here's how they map to Ankify:

- **Resource Owner**: The human user who owns the account and data. They decide whether Claude Desktop should be allowed to use Ankify on their behalf.
- **Client**: Claude Desktop (or Cursor, or any MCP client). It wants to call Ankify's tools but has no credentials of its own — it needs the user's permission.
- **Authorization Server (AS)**: AWS Cognito's User Pool. It knows user identities, handles login, and mints tokens. It's the trusted bouncer.
- **Resource Server (RS)**: Your Ankify MCP server running on Lambda. It accepts tokens, validates them, and serves flashcard-generation tools.

### OAuth 2.1 vs. 2.0: a security cleanup

OAuth 2.0 (RFC 6749, 2012) defined several "grant types" — ways to get tokens. Over a decade of real-world attacks revealed that two of those flows were fundamentally insecure. **OAuth 2.1** (draft-ietf-oauth-v2-1-14, currently in late-stage IETF review) consolidates a decade of security lessons into a single spec. The key changes:

- **The Implicit Grant is gone.** It returned tokens directly in URL fragments, exposing them to browser history, referrer headers, and JavaScript on the page. It existed as a CORS workaround that's no longer needed.
- **The Resource Owner Password Credentials Grant is gone.** It let apps collect user passwords directly — the exact anti-pattern OAuth was designed to eliminate.
- **PKCE is mandatory for all clients**, not just mobile apps (more on this below).
- **Redirect URIs must match exactly** — no more wildcards that attackers could exploit.
- **Bearer tokens in URL query strings are prohibited** — URLs get logged everywhere.

What remains are **two core grants**: the Authorization Code flow (for users) and Client Credentials (for machine-to-machine). MCP uses the Authorization Code flow.

---

## Part 2: The Authorization Code flow, step by step

The Authorization Code flow is the heartbeat of OAuth. It's redirect-based, meaning the user's browser bounces between the client and the authorization server. This design is deliberate: **the client application never touches the user's password.** The user authenticates directly with the authorization server (Cognito's Hosted UI), and the client only ever receives a token.

The flow uses two endpoints on the Authorization Server:

- **`/authorize`** (front-channel): The user's browser visits this. It handles login and consent. It returns an **authorization code** via redirect — a short-lived, single-use receipt.
- **`/token`** (back-channel): The client's server calls this directly (no browser involved). It exchanges the authorization code for actual tokens. Because this is server-to-server over HTTPS, the tokens are never exposed to the browser.

Here's the flow in concrete Ankify terms:

**Step 1 — Claude Desktop redirects the user to Cognito.** It constructs a URL like:
```
GET https://ankify.auth.us-east-1.amazoncognito.com/oauth2/authorize?
    response_type=code
    &client_id=abc123
    &redirect_uri=http://localhost:54321/callback
    &scope=ankify.example.com/generate_deck
    &state=random_csrf_string
    &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
    &code_challenge_method=S256
```

The `state` parameter is a random string Claude Desktop remembers. When Cognito redirects back, it echoes `state` so Claude Desktop can verify it's the same flow (prevents CSRF attacks). The `code_challenge` is part of PKCE — covered next.

**Step 2 — The user logs in at Cognito's Hosted UI.** Cognito shows its login page. The user enters their username and password (or uses Google SSO, or whatever you've configured). Claude Desktop never sees these credentials.

**Step 3 — Cognito redirects back with an authorization code:**
```
HTTP/1.1 302 Found
Location: http://localhost:54321/callback?code=SplxlOBeZQQYbYS6WxSbIA&state=random_csrf_string
```

This `code` is **not a token**. It's a single-use, short-lived (typically 5 minutes) receipt that proves the user authenticated and consented.

**Step 4 — Claude Desktop exchanges the code for tokens** via a direct HTTPS POST (no browser):
```
POST /oauth2/token HTTP/1.1
Host: ankify.auth.us-east-1.amazoncognito.com
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=SplxlOBeZQQYbYS6WxSbIA
&redirect_uri=http://localhost:54321/callback
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
```

**Step 5 — Cognito returns the tokens:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "IwOGYzYTlmM2YxOTQ5..."
}
```

Now Claude Desktop can call Ankify by including `Authorization: Bearer eyJhbGciOiJSUzI1NiIs...` in every request. But why the two-step dance (code, then token)? Because the authorization code travels through the browser (front-channel) where it could be intercepted. The actual tokens travel only server-to-server (back-channel). Even if someone sniffs the code, they can't use it without the `code_verifier` — which brings us to PKCE.

---

## Part 3: PKCE — proving you're the one who started the flow

**PKCE** (pronounced "pixy," RFC 7636) solves a specific attack: **authorization code interception.** Here's the scenario. Claude Desktop starts an OAuth flow and the user authenticates. Cognito redirects back to `http://localhost:54321/callback?code=ABC123`. But what if a malicious app on the user's machine is also listening on that port, or registers a handler for the same custom URL scheme? The attacker grabs the code and exchanges it for tokens before Claude Desktop can.

PKCE prevents this with a cryptographic "proof of origin." It works like a sealed envelope:

**Before the flow starts**, Claude Desktop generates two values:
- A **`code_verifier`**: a long random string (43–128 characters), e.g., `dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk`
- A **`code_challenge`**: the SHA-256 hash of the verifier, Base64URL-encoded, e.g., `E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM`

In the `/authorize` request, Claude Desktop sends only the **`code_challenge`** (the hash). Cognito stores it alongside the authorization code. Later, when exchanging the code at `/token`, Claude Desktop sends the original **`code_verifier`** (the plaintext). Cognito hashes it and compares: if `SHA256(code_verifier) == stored code_challenge`, the exchange succeeds.

**Why this defeats the attacker:** The attacker intercepted the code but never saw the `code_verifier` — that was generated locally in Claude Desktop's memory and only sent over the back-channel HTTPS POST to `/token`. The `code_challenge` (hash) traveled through the browser, but SHA-256 is a one-way function — knowing the hash doesn't reveal the original string. **The attacker has the code but can't prove they started the flow.**

OAuth 2.1 mandates PKCE for *all* clients — including server-side apps that have a `client_secret`. The reasoning: even confidential clients benefit from defense-in-depth, and it also prevents authorization code injection attacks where an attacker substitutes their own code into someone else's session.

---

## Part 4: JWTs — self-contained tokens you can verify without a database call

When Cognito issues an access token, it's not an opaque random string — it's a **JSON Web Token (JWT)**, pronounced "jot" (RFC 7519). A JWT is a compact, self-contained package that encodes the user's identity and permissions directly into the token itself, signed cryptographically so anyone can verify it hasn't been tampered with.

### Three parts, separated by dots

A JWT looks like this: `eyJhbGci.eyJzdWIi.SflKxwRJ` — three Base64URL-encoded segments:

**1. Header** — metadata about the token:
```json
{
  "alg": "RS256",
  "typ": "JWT",
  "kid": "us-east-1_abc123_key1"
}
```
The `alg` field says the signing algorithm is **RS256** (RSA + SHA-256). The `kid` (Key ID) identifies which specific key signed this token — critical for key rotation.

**2. Payload** — the claims (statements about the user and token):
```json
{
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123",
  "sub": "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111",
  "aud": "https://ankify.example.com",
  "exp": 1700000000,
  "iat": 1699996400,
  "scope": "ankify.example.com/generate_deck",
  "client_id": "abc123"
}
```

Key claims: **`iss`** (issuer — who minted this), **`sub`** (subject — which user), **`aud`** (audience — which server this is for), **`exp`** (expiration — Unix timestamp), **`scope`** (what permissions were granted). The payload is *not encrypted* — anyone can Base64-decode it and read the claims. The security comes from the signature.

**3. Signature** — the cryptographic proof:
```
RS256(base64url(header) + "." + base64url(payload), private_key)
```

Cognito signs the token with its **private key**. Your Ankify server (or anyone) can verify it with Cognito's **public key**. If anyone modifies a single character in the header or payload, the signature check fails.

### Why JWTs matter for Lambda

This is the critical insight for serverless architectures: **JWT verification is stateless.** When a request hits your Lambda function with a Bearer token, your code doesn't need to call Cognito or query a database to check if the token is valid. It just:
1. Decodes the header to get the `kid`
2. Fetches Cognito's public keys (cached)
3. Verifies the signature mathematically
4. Checks `exp`, `iss`, `aud` claims

This is a pure in-memory cryptographic operation — **no network call, no database read, no shared session state.** For Lambda functions that spin up and down constantly with no shared memory between invocations, this is exactly what you need.

### Access tokens vs. ID tokens

Cognito issues both, and they serve different purposes:

- **Access token**: Sent to the Resource Server (Ankify). Contains scopes/permissions. The `aud` claim is the API. Used in the `Authorization: Bearer` header. This is what authorizes API access.
- **ID token**: Consumed by the Client (Claude Desktop). Contains user profile info (`name`, `email`). The `aud` claim is the client's `client_id`. Proves the user's identity to the app. **Never send this to an API.**

For MCP, only the access token matters for authenticating requests to Ankify.

---

## Part 5: JWKS — how your server finds the right public key

Your Ankify server needs Cognito's public key to verify JWT signatures. But Cognito rotates keys periodically for security, and you don't want to hardcode keys or redeploy every time they change. This is where **JWKS (JSON Web Key Set, RFC 7517)** comes in.

Cognito publishes its current public keys at a well-known URL:
```
https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123/.well-known/jwks.json
```

The response is a JSON document listing all active public keys:
```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "us-east-1_abc123_key1",
      "use": "sig",
      "alg": "RS256",
      "n": "oahUIoWw0K0usKNuOR6H...",
      "e": "AQAB"
    },
    {
      "kty": "RSA",
      "kid": "us-east-1_abc123_key2",
      "use": "sig",
      "alg": "RS256",
      "n": "sfsXMXWuO-dkqj83hf2...",
      "e": "AQAB"
    }
  ]
}
```

Each key has a **`kid`** (Key ID), an **`n`** (RSA modulus), and an **`e`** (exponent) — together these reconstruct the RSA public key. The verification flow is:

1. Extract the `kid` from the JWT's header (e.g., `"us-east-1_abc123_key1"`)
2. Fetch the JWKS from Cognito (cache this — don't fetch on every request)
3. Find the key in the `keys` array whose `kid` matches
4. Construct the RSA public key from `n` and `e`
5. Verify the JWT signature using this public key
6. If valid, check the claims (`exp`, `iss`, `aud`)

**Key rotation happens seamlessly**: Cognito adds a new key to the JWKS, starts signing new tokens with it (new `kid`), and keeps the old key around until all tokens signed with it expire. Your server just re-fetches JWKS when it encounters an unknown `kid`.

---

## Part 6: Dynamic Client Registration — how strangers introduce themselves

In traditional OAuth, you manually register your app with each service. You log into the Google Developer Console, create an OAuth app, get a `client_id` and `client_secret`, and hardcode them. This works when one app talks to one known service. **It completely breaks down in MCP.**

Think about it: Claude Desktop needs to connect to *any* MCP server the user wants — Ankify, a weather server, a database tool, hundreds of community servers. Claude Desktop's developers can't pre-register with every possible MCP server. And each MCP server operator can't pre-register every possible MCP client. The combinatorics are impossible.

**Dynamic Client Registration (DCR, RFC 7591)** solves this by letting clients register programmatically. Instead of a human filling out a form, the client sends a POST request:

```http
POST /register HTTP/1.1
Host: ankify.example.com
Content-Type: application/json

{
  "client_name": "Claude Desktop",
  "redirect_uris": ["http://localhost:54321/callback"],
  "grant_types": ["authorization_code"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

The server responds with freshly minted credentials:
```json
{
  "client_id": "generated_unique_id_789",
  "client_id_issued_at": 1700000000,
  "redirect_uris": ["http://localhost:54321/callback"],
  "grant_types": ["authorization_code"],
  "token_endpoint_auth_method": "none"
}
```

Now Claude Desktop has a `client_id` to use in the OAuth flow — no human intervention required. Note `token_endpoint_auth_method: "none"` — Claude Desktop is a **public client** (it can't keep a secret since it runs on the user's machine), so it gets no `client_secret`. PKCE provides the security instead.

It's worth noting that the MCP spec has evolved here: the **November 2025 revision** introduced **Client ID Metadata Documents (CIMD)** as the preferred registration mechanism, with DCR downgraded to a backwards-compatibility option. CIMD works differently — the client hosts a JSON document at a stable URL (like `https://claude.ai/.well-known/oauth-client.json`) that the server can fetch. But DCR remains widely implemented and is what FastMCP's `AWSCognitoProvider` uses today.

---

## Part 7: Resource Indicators — making sure tokens can't be misused

Here's a subtle but critical attack that OAuth's basic `scope` mechanism doesn't prevent. Suppose you have two MCP servers: Ankify (flashcard generation) and BankBot (financial data). A user authenticates with both through the same Cognito User Pool. Without additional protection, a token issued for Ankify could theoretically be presented to BankBot — and if BankBot only checks "is this token from our Cognito pool?" it would accept it.

**Resource Indicators (RFC 8707)** close this gap by adding a `resource` parameter to OAuth requests. The client tells the Authorization Server exactly which Resource Server the token is for:

```
GET /authorize?...&resource=https://ankify.example.com
```
```
POST /token ...&resource=https://ankify.example.com
```

The AS then **audience-restricts** the token — the JWT's `aud` claim is set to `https://ankify.example.com`. When Ankify receives the token, it checks: "Is my URL in the `aud` claim?" If yes, valid. If someone tries to use this token at BankBot, BankBot checks `aud`, sees it says `ankify.example.com`, and rejects it.

**MCP mandates resource indicators.** Clients MUST include the `resource` parameter in both authorization and token requests, and MCP servers MUST validate that tokens are audience-restricted to them. This prevents **token mis-redemption** — a particularly dangerous attack in the MCP ecosystem where users connect to many servers through the same identity provider.

---

## Part 8: Bearer tokens — the simplest concept with the scariest implication

After all the complexity above, actually *using* a token is refreshingly simple. When Claude Desktop calls Ankify, it includes the token in the HTTP `Authorization` header:

```http
POST /mcp HTTP/1.1
Host: ankify.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json

{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "generate_deck", "arguments": {"topic": "mitochondria"}}}
```

The word **"Bearer"** means exactly what it sounds like: whoever *bears* (carries) this token gets access. There's no additional cryptographic proof required — no client certificate, no signed request. It's like a concert ticket: if you have it, you're in. This simplicity is why bearer tokens MUST only travel over HTTPS (encrypted in transit), must be short-lived (typically **1 hour**), and must never appear in URLs (which get logged).

---

## Part 9: The complete MCP OAuth flow, end to end

Now let's trace every single HTTP request in the full MCP authentication flow for Ankify. This is the master sequence that ties everything together.

### Step 1: Initial unauthenticated request → 401

Claude Desktop doesn't know yet whether Ankify requires authentication. It tries a normal MCP request:

```http
POST /mcp HTTP/1.1
Host: ankify.example.com
Content-Type: application/json

{"jsonrpc": "2.0", "method": "initialize", "params": {...}}
```

Ankify responds: **"You need to authenticate."**

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer resource_metadata="https://ankify.example.com/.well-known/oauth-protected-resource"
```

**Why this step exists:** The 401 with `WWW-Authenticate` is the standard HTTP mechanism for signaling "auth required." The `resource_metadata` URL tells the client where to discover authentication details. This is the trigger for the entire OAuth flow.

### Step 2: Discover Protected Resource Metadata (RFC 9728)

Claude Desktop fetches the URL from the 401 response:

```http
GET /.well-known/oauth-protected-resource HTTP/1.1
Host: ankify.example.com
```

Response:
```json
{
  "resource": "https://ankify.example.com/mcp",
  "authorization_servers": ["https://ankify.example.com"],
  "scopes_supported": ["ankify.example.com/generate_deck", "ankify.example.com/list_decks"]
}
```

**Why this step exists:** This tells Claude Desktop two critical things: (1) the canonical URI of the resource (used as the `resource` parameter in RFC 8707), and (2) which Authorization Server to talk to. Note that `authorization_servers` points to Ankify itself — because FastMCP's `AWSCognitoProvider` acts as a proxy AS, not directly to Cognito.

### Step 3: Discover Authorization Server Metadata (RFC 8414)

Claude Desktop now fetches the AS metadata:

```http
GET /.well-known/oauth-authorization-server HTTP/1.1
Host: ankify.example.com
```

Response (served by FastMCP's proxy):
```json
{
  "issuer": "https://ankify.example.com/",
  "authorization_endpoint": "https://ankify.example.com/authorize",
  "token_endpoint": "https://ankify.example.com/token",
  "registration_endpoint": "https://ankify.example.com/register",
  "jwks_uri": "https://ankify.example.com/.well-known/jwks.json",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"]
}
```

**Why this step exists:** Now Claude Desktop knows every URL it needs: where to register, where to send the user for login, where to exchange codes for tokens, and where to find public keys. If `code_challenge_methods_supported` doesn't include `S256`, the MCP spec says the client MUST refuse to proceed — no PKCE means no security.

### Step 4: Dynamic Client Registration

Claude Desktop registers itself:

```http
POST /register HTTP/1.1
Host: ankify.example.com
Content-Type: application/json

{
  "client_name": "Claude Desktop",
  "redirect_uris": ["http://localhost:54321/callback"],
  "grant_types": ["authorization_code"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

FastMCP's proxy stores this registration in DynamoDB and responds:

```json
{
  "client_id": "proxy_generated_id_456",
  "redirect_uris": ["http://localhost:54321/callback"],
  "grant_types": ["authorization_code"],
  "token_endpoint_auth_method": "none"
}
```

**Why this step exists:** Claude Desktop now has a `client_id` for this specific MCP server. Behind the scenes, FastMCP's proxy stored the client's redirect URI pattern and will use its *own* pre-registered Cognito app client credentials when talking upstream to Cognito. The MCP client doesn't know or care about this indirection.

### Step 5: Authorization Code + PKCE flow initiation

Claude Desktop generates PKCE values locally:
```
code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"  (random, kept secret)
code_challenge = BASE64URL(SHA256(code_verifier))  (sent in the request)
```

Then opens the user's browser to:
```
GET https://ankify.example.com/authorize?
    response_type=code
    &client_id=proxy_generated_id_456
    &redirect_uri=http://localhost:54321/callback
    &scope=ankify.example.com/generate_deck
    &state=xcoiv98y2kd
    &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
    &code_challenge_method=S256
    &resource=https://ankify.example.com/mcp
```

FastMCP's proxy receives this, creates an **`OAuthTransaction`** in DynamoDB (storing the client's PKCE challenge, state, redirect URI, and scopes), shows a consent screen, then generates its *own* PKCE pair for the upstream Cognito request and redirects to Cognito:

```
GET https://ankify.auth.us-east-1.amazoncognito.com/oauth2/authorize?
    response_type=code
    &client_id=cognito_app_client_id
    &redirect_uri=https://ankify.example.com/auth/callback
    &scope=ankify.example.com/generate_deck
    &state=proxy_internal_state
    &code_challenge=PROXY_GENERATED_CHALLENGE
    &code_challenge_method=S256
```

**Why this step exists:** The proxy acts as an intermediary — it receives Claude Desktop's OAuth request, and forwards it upstream to Cognito with its own registered credentials. The user doesn't notice the indirection.

### Step 6: User authenticates at Cognito Hosted UI

Cognito shows its login page. The user enters their username and password (or uses social login). They may see a consent screen for the requested scopes. After successful authentication, Cognito redirects back to the proxy's callback:

```
HTTP/1.1 302 Found
Location: https://ankify.example.com/auth/callback?code=COGNITO_AUTH_CODE&state=proxy_internal_state
```

### Step 7: Proxy exchanges Cognito's code for tokens (server-side)

FastMCP's proxy makes a back-channel request to Cognito:

```http
POST /oauth2/token HTTP/1.1
Host: ankify.auth.us-east-1.amazoncognito.com
Content-Type: application/x-www-form-urlencoded
Authorization: Basic base64(cognito_client_id:cognito_client_secret)

grant_type=authorization_code
&code=COGNITO_AUTH_CODE
&redirect_uri=https://ankify.example.com/auth/callback
&code_verifier=PROXY_CODE_VERIFIER
```

Cognito returns tokens. The proxy **encrypts and stores these upstream tokens in DynamoDB** (the `mcp-upstream-tokens` collection) — they never leave the server. It then generates a **new authorization code** for Claude Desktop, stores it in DynamoDB's `mcp-authorization-codes` collection, and redirects the user's browser back to Claude Desktop:

```
HTTP/1.1 302 Found
Location: http://localhost:54321/callback?code=PROXY_AUTH_CODE&state=xcoiv98y2kd
```

### Step 8: Claude Desktop exchanges the proxy's code for a FastMCP JWT

Claude Desktop verifies the `state` matches, then makes a back-channel POST:

```http
POST /token HTTP/1.1
Host: ankify.example.com
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=PROXY_AUTH_CODE
&redirect_uri=http://localhost:54321/callback
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
&resource=https://ankify.example.com/mcp
```

The proxy validates Claude Desktop's `code_verifier` against the stored `code_challenge`, then issues its **own JWT** (not Cognito's token). It creates a **JTI mapping** in DynamoDB linking this JWT's unique ID to the stored upstream Cognito tokens:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...(FastMCP-signed JWT)",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "fastmcp_refresh_token_xyz"
}
```

### Step 9: Authenticated MCP requests

Claude Desktop now calls Ankify with the Bearer token:

```http
POST /mcp HTTP/1.1
Host: ankify.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json

{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "generate_deck", "arguments": {"topic": "mitochondria"}}}
```

FastMCP validates the JWT (checks signature via its own JWKS, verifies `exp`, `aud`, `iss`), looks up the JTI mapping in DynamoDB to find the upstream Cognito tokens if needed, and processes the request. **Response: 200 OK with your Anki deck.**

---

## Part 10: What FastMCP's AWSCognitoProvider actually does for you

Building the proxy layer described above from scratch would be a significant engineering project. FastMCP's `AWSCognitoProvider` (introduced in **v2.12.4**, September 2025) handles it automatically by extending the `OAuthProxy` base class. Here's what it provides:

**It bridges MCP's requirements to Cognito's capabilities.** The fundamental problem is that Cognito doesn't support Dynamic Client Registration (RFC 7591) — you can't programmatically create app clients via an API call to a registration endpoint. The `AWSCognitoProvider` solves this by accepting DCR requests from MCP clients, storing client metadata locally, and using a single pre-registered Cognito app client for all upstream authentication. All MCP clients share the same upstream Cognito credentials, but each gets a unique proxy-level `client_id`.

**It auto-constructs all Cognito endpoints** from just the `user_pool_id` and `aws_region`. Given `user_pool_id="us-east-1_AbC123"` and region `"us-east-1"`, it knows the authorize, token, and JWKS URLs without you specifying them.

**It serves the `.well-known` discovery endpoints** that MCP requires — both the `oauth-authorization-server` metadata and `oauth-protected-resource` metadata — pointing to its own proxy endpoints rather than directly to Cognito.

**It issues its own JWTs** (since v2.13.0) rather than passing through Cognito's tokens. This is important because the proxy needs tokens scoped to the MCP server's audience, not Cognito's internal audience. The JTI mapping in DynamoDB connects each FastMCP JWT back to the corresponding Cognito token.

**It handles the consent screen**, adding CSRF protection to prevent confused deputy attacks where a malicious client tricks a user into authorizing the wrong operation.

**It manages all encryption and storage** through the `py-key-value-aio` library with automatic Fernet encryption (AES-128-CBC + HMAC-SHA256) for tokens at rest.

A minimal configuration looks like:
```python
from fastmcp import FastMCP
from fastmcp.server.auth.providers.aws import AWSCognitoProvider

auth = AWSCognitoProvider(
    user_pool_id="us-east-1_AbC123",
    aws_region="us-east-1",
    client_id="your_cognito_app_client_id",
    client_secret="your_cognito_app_client_secret",
    base_url="https://ankify.example.com",
)

mcp = FastMCP("Ankify", auth=auth)
```

Everything else — DCR endpoint, authorize endpoint, token endpoint, callback handling, JWKS endpoint, metadata endpoints, PKCE validation, token encryption, DynamoDB storage — is handled automatically.

---

## Part 11: AWS Cognito's role in the stack

Cognito is your identity provider — the service that actually knows who your users are and verifies their credentials. Two concepts matter here:

**User Pools vs. Identity Pools — and why you only need a User Pool.** A Cognito User Pool is a full OAuth 2.0 / OIDC authorization server. It stores user accounts, handles sign-up/sign-in, issues JWTs, and exposes standard OAuth endpoints. An Identity Pool (now called "Cognito Identity") is a different thing entirely — it exchanges tokens from various identity providers for temporary *AWS IAM credentials* (to access S3, DynamoDB, etc. directly from client code). **For MCP server auth, you only need a User Pool.** You're authenticating users to your application, not granting them direct access to AWS services.

**Hosted UI** is Cognito's pre-built login page. When users are redirected during the OAuth flow, they land on a Cognito-branded (customizable) page that handles username/password login, social sign-in (Google, Facebook, Apple), MFA, password reset, and new account registration. You get all of this without building a single login page. The URL follows the pattern `https://{domain}.auth.{region}.amazoncognito.com/oauth2/authorize`.

**App Clients** are Cognito's equivalent of OAuth client registrations. Each app client gets a `client_id` and optionally a `client_secret`. You configure which OAuth flows it supports (authorization code, client credentials), which callback URLs are allowed, and which scopes it can request. For Ankify's `AWSCognitoProvider`, you create **one** app client configured as a "Traditional web application" with the authorization code grant and your proxy's callback URL.

**Resource Servers** in Cognito define custom OAuth scopes. You register a Resource Server with an identifier (e.g., `ankify.example.com`) and define scopes like `generate_deck` and `list_decks`. In tokens, these appear as `ankify.example.com/generate_deck`. This identifier **must exactly match** your `base_url` + MCP path — a mismatch causes `invalid_grant` errors at token exchange. This is Cognito's mechanism for implementing the audience restriction that RFC 8707 requires.

---

## Part 12: Why DynamoDB is essential for Lambda-based OAuth

Lambda functions are stateless and ephemeral. Each invocation may run in a different container, and containers can be recycled between requests. Yet the OAuth flow described above spans **multiple HTTP requests** — the authorize request, the callback, the token exchange — that may hit different Lambda instances. This means every piece of OAuth state must live in an external store.

FastMCP's OAuth proxy uses **six storage collections**, each serving a distinct purpose:

**`mcp-oauth-proxy-clients`** stores DCR registrations. When Claude Desktop registers via `POST /register`, the client's metadata (name, redirect URIs, allowed patterns) is stored here. This persists indefinitely — the client doesn't need to re-register on every session.

**`mcp-oauth-transactions`** tracks in-flight authorization flows. When a user hits `/authorize`, the proxy creates a transaction storing the client's PKCE challenge, state parameter, redirect URI, requested scopes, and CSRF token. TTL: ~15 minutes. Deleted after the callback completes.

**`mcp-authorization-codes`** stores the proxy-generated authorization codes (not Cognito's codes). Each entry contains the code, the bound PKCE challenge, and references to the upstream tokens. TTL: 5 minutes. Single-use — deleted after exchange.

**`mcp-upstream-tokens`** holds the encrypted Cognito access and refresh tokens obtained during the callback phase. These are the "real" tokens from Cognito, encrypted with Fernet before storage. They never leave the server.

**`mcp-jti-mappings`** links each FastMCP-issued JWT (via its `jti` claim) to the corresponding upstream token set. When Ankify receives a request with a FastMCP JWT, it validates the JWT statelessly, then uses the JTI mapping to look up the upstream Cognito tokens if it needs to check Cognito-specific claims or permissions.

**`mcp-refresh-tokens`** stores metadata about issued refresh tokens, indexed by hash, supporting token rotation and revocation.

DynamoDB is the natural choice for this because it's serverless (no infrastructure to manage), offers single-digit millisecond latency, supports **TTL-based automatic expiration** (perfectly matching OAuth's short-lived codes and tokens), integrates with Lambda via IAM roles (no connection strings), and provides encryption at rest. In FastMCP, the storage backend is pluggable via the `py-key-value-aio` library — you could also use Redis or MongoDB — but DynamoDB best fits the serverless model.

---

## Conclusion: the map of the territory

The OAuth stack for MCP servers is deep but logical once you see how each piece solves a specific problem. **OAuth 2.1** establishes the framework: delegate authorization without sharing credentials. The **Authorization Code flow** keeps passwords away from clients by using browser redirects and back-channel token exchange. **PKCE** ensures stolen authorization codes are useless without the original verifier. **JWTs** make tokens self-verifiable — critical for Lambda's stateless execution model. **JWKS** publishes the public keys needed for that verification. **DCR** lets unknown MCP clients register on the fly. **Resource Indicators** prevent tokens from being misused across different servers. And **FastMCP's `AWSCognitoProvider`** stitches all of this together into a proxy layer that bridges Cognito's standard OAuth with MCP's specific requirements, using DynamoDB to persist the multi-step flow state that Lambda can't hold in memory.

The key mental model is **two OAuth flows nested inside each other**: the outer flow between the MCP client and FastMCP's proxy, and the inner flow between the proxy and Cognito. The proxy translates between them, issuing its own tokens while storing Cognito's tokens securely. Every `.well-known` endpoint, every redirect, every code exchange has a precise purpose in this chain — and now you know what each one does and why it's there.