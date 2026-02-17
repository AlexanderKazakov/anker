# Ankify AWS deployment: CloudFront, auth, and SPA for under $1/month

**Your full Level 2 + Level 3 stack will cost roughly $0.50/month** for ~100 users and ~500 deck generations — Route 53's $0.50 hosted zone fee is the only meaningful fixed cost. Every other service falls within AWS free tiers. The critical gotcha is **CloudFront's default 30-second origin response timeout**, which will silently kill your 30–60 second TTS requests with 504 errors unless you raise it to at least 90 seconds via a quota increase request. Below is the complete deployment blueprint with exact pricing, configuration details, and every non-obvious trap identified.

---

## CloudFront sits between users and Lambda with two careful timeout settings

CloudFront pricing offers two models. The **pay-as-you-go always-free tier** provides **1 TB data transfer and 10 million HTTPS requests per month** — perpetual, not limited to the first 12 months. For a hobby project serving ~62,000 requests and ~3 GB of data monthly, this costs exactly $0.00. Alternatively, AWS launched **flat-rate pricing plans** in November 2025: the Free plan ($0/month) bundles CloudFront + WAF (5 rules) + Route 53 DNS + S3 storage credits + DDoS protection into one package, but with lower limits (1M requests, 100 GB data). The flat-rate Free plan eliminates the $0.50/month Route 53 cost and adds WAF for free, but restricts Lambda@Edge and custom header policies. For pay-as-you-go Europe pricing, data transfer runs **$0.085/GB** and HTTPS requests cost **$0.01 per 10,000**.

**The timeout configuration is non-negotiable.** CloudFront's origin response timeout defaults to **30 seconds**, configurable up to 60 seconds in the console, and up to **180 seconds via a quota increase** through AWS Support. Your TTS operations (30–60s) plus Docker cold starts (2–5s) mean you need **at minimum 90 seconds**, which requires filing a support case. Without this change, every long-running MCP request will return a 504 Gateway Timeout. Set the **Response Completion Timeout** to at least 120 seconds as well — this is the total time CloudFront waits for the complete response, distinct from the per-packet origin response timeout.

For the Lambda Function URL origin, use **Origin Access Control (OAC)** with `SigningBehavior: always` and `SigningProtocol: sigv4`. The Lambda Function URL should have `AuthType: AWS_IAM`. You must add a resource-based policy to the Lambda function:

```bash
aws lambda add-permission \
  --statement-id "AllowCloudFrontServicePrincipal" \
  --action "lambda:InvokeFunctionUrl" \
  --principal "cloudfront.amazonaws.com" \
  --source-arn "arn:aws:cloudfront::ACCOUNT_ID:distribution/DISTRIBUTION_ID" \
  --function-name FUNCTION_NAME
```

**Critical header gotcha:** Use the managed origin request policy **`AllViewerExceptHostHeader`** — never forward the Host header to Lambda Function URLs, or you'll get unexplained 403 errors. CloudFront auto-sets the Host header to the Lambda Function URL domain.

For POST requests through CloudFront with OAC, the `x-amz-content-sha256` header may be required. This is a known complication for OAC + POST bodies. An alternative is `AuthType: NONE` on the Function URL with a custom secret header validated in your Lambda code.

### Route 53, ACM, and domain costs

Route 53 costs **$0.50/month per hosted zone** — confirmed, no free tier. Alias A/AAAA records pointing to CloudFront distributions are **free** (no per-query charge). Standard queries cost $0.40 per million. For domain registration, **Cloudflare Registrar** sells at wholesale cost (~$10–11/year for .com) versus Route 53's ~$13–14/year. You can register externally and point nameservers to Route 53.

ACM public certificates are **free** when used with CloudFront, confirmed at the ACM pricing page. The one gotcha: **certificates for CloudFront must be created in us-east-1**, regardless of where your Lambda runs. ACM auto-renews certificates 60 days before expiration.

---

## Cognito authentication at zero cost with FastMCP's built-in provider

### Cognito pricing after the December 2024 restructure

Cognito now has three tiers. **Lite** and **Essentials** both offer **10,000 MAU free** (perpetual, not time-limited). For 100 users/month, authentication costs exactly **$0.00**. After free tier, Lite charges $0.0055/MAU (tiered) and Essentials charges $0.015/MAU flat. New user pools default to Essentials — switch to **Lite** if you only need basic password auth, social login, and TOTP MFA. The Plus tier ($0.020/MAU) has **no free tier** and adds threat protection features you don't need.

**Hidden cost traps to avoid:** SMS-based MFA verification charges $0.01–$0.04 per message via SNS — use **TOTP (authenticator app) MFA instead**, which is free. Never enable Advanced Security Features on Lite tier — they add **$0.05/MAU**, which at 100 users costs $5/month, dwarfing your entire infrastructure bill. Cognito Hosted UI and Lambda triggers (pre-token generation, etc.) incur no additional charge beyond normal Lambda invocation costs.

The Hosted UI supports **Google, Facebook, Apple, Amazon** natively, and **GitHub via OIDC federation**. It can be customized with logos and CSS (Lite) or a visual branding editor (Essentials+). The same Cognito User Pool serves both MCP OAuth and SPA login — create **separate app clients** for each. You only need a **User Pool**, not an Identity Pool (Identity Pools are for granting temporary AWS credentials to end users, which isn't your use case).

### The MCP OAuth flow end-to-end

When an MCP client like Claude Desktop connects to your authenticated server, the flow is:

1. Client sends initial request → server returns **401** with `WWW-Authenticate` header containing `resource_metadata` URL
2. Client fetches `/.well-known/oauth-protected-resource` from the MCP server → gets authorization server URL
3. Client fetches `/.well-known/oauth-authorization-server` → gets authorize/token/register endpoints
4. Client performs **Dynamic Client Registration** (RFC 7591) to obtain a `client_id`
5. Client initiates **Authorization Code + PKCE flow** → redirects user to Cognito Hosted UI
6. User authenticates → Cognito redirects back with authorization code
7. Client exchanges code + PKCE verifier for access token
8. All subsequent MCP requests include `Authorization: Bearer <token>`

The MCP spec mandates **OAuth 2.1 with PKCE** and **Resource Indicators (RFC 8707)**. FastMCP's `AWSCognitoProvider` handles all of this automatically — it proxies between MCP's DCR requirement and Cognito's standard OAuth, issues its own JWTs to MCP clients, and validates tokens against Cognito's JWKS endpoint.

### Alternative auth approaches

For the simplest possible setup, FastMCP provides `TokenVerifier` and `StaticTokenVerifier` for bare Bearer token validation. However, spec-compliant MCP clients expect the full OAuth discovery flow. A practical hybrid: **Cognito for both SPA and MCP** via `AWSCognitoProvider` (since it's zero cost at this scale anyway). Compared to alternatives — Auth0 gives 25,000 free MAU but paid starts at $35/month; Supabase Auth offers 50,000 free MAU but projects pause after 7 days of inactivity on the free tier. Cognito wins for AWS-native deployments.

---

## FastMCP configuration for Lambda: DynamoDB storage, stateless mode, and mounting

### DynamoDB as the OAuth state backend

The `AWSCognitoProvider` extends `OAuthProxy`, which needs persistent storage for five collections: client registrations, in-flight OAuth transactions (PKCE state), authorization codes, upstream Cognito tokens (encrypted), and JWT-ID-to-token mappings. On Lambda, the default in-memory storage loses state between invocations. The solution is `py-key-value-aio` with the DynamoDB backend:

```python
from fastmcp import FastMCP
from fastmcp.server.auth.providers.aws import AWSCognitoProvider
from key_value.aio.stores.dynamodb import DynamoDBStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from cryptography.fernet import Fernet

dynamodb_store = DynamoDBStore(
    table_name="fastmcp-oauth-state",
    region_name="eu-central-1"
)

auth_provider = AWSCognitoProvider(
    user_pool_id="eu-central-1_XXXXXXXXX",
    aws_region="eu-central-1",
    client_id=os.environ["COGNITO_CLIENT_ID"],
    client_secret=os.environ["COGNITO_CLIENT_SECRET"],
    base_url="https://your-domain.com",
    jwt_signing_key=os.environ["JWT_SIGNING_KEY"],
    client_storage=FernetEncryptionWrapper(
        key_value=dynamodb_store,
        fernet=Fernet(os.environ["STORAGE_ENCRYPTION_KEY"])
    )
)

mcp = FastMCP(name="Ankify", auth=auth_provider, stateless_http=True)
app = mcp.http_app()
```

Install with `pip install py-key-value-aio[dynamodb]`. The DynamoDB backend uses boto3 underneath and automatically picks up the Lambda execution role's IAM permissions. **One caveat:** FastMCP's docs rate DynamoDB as "✅ Best (AWS)" for cloud-native deployments but note that the py-key-value DynamoDB backend has sparse documentation — Redis is more battle-tested. For a hobby project, DynamoDB is the right choice since it requires no infrastructure management.

**Cognito Resource Server setup is critical:** Create a Resource Server in your Cognito User Pool with an identifier matching `{base_url}/mcp` (e.g., `https://ankify.yourdomain.com/mcp`). Without this, token scoping will fail silently.

DynamoDB on-demand pricing: **$1.25 per million writes, $0.25 per million reads**, with 25 GB free storage (perpetual). At ~200 OAuth operations/month, your bill rounds to **$0.00**. TTL deletions for expired OAuth state are completely free.

### stateless_http=True is mandatory for Lambda

This flag makes each HTTP request create a fresh transport context with no server-side session persistence. It's **required** for Lambda because session state doesn't survive across invocations. It's **fully compatible with OAuth** — all OAuth state lives in `client_storage` (DynamoDB), not in MCP sessions. The flag works with StreamableHTTP transport and SSE streaming within individual requests.

### Mount into FastAPI for REST endpoints, not custom_route

FastMCP's `@mcp.custom_route()` works for simple health checks but **doesn't inherit MCP OAuth authentication** and lacks request validation, dependency injection, and API documentation. For the SPA's deck generation REST endpoints, **mount FastMCP into a FastAPI application**:

```python
from fastapi import FastAPI, Depends, Request
from fastmcp import FastMCP

mcp = FastMCP("Ankify", auth=auth_provider, stateless_http=True)
mcp_app = mcp.http_app(path="/")

api = FastAPI(lifespan=mcp_app.lifespan)  # lifespan is REQUIRED

@api.post("/api/decks")
async def create_deck(request: Request):
    # Validate Cognito JWT from Authorization header
    # Deck generation logic
    pass

api.mount("/mcp", mcp_app)
```

When mounting with OAuth, you must handle `.well-known` discovery routes at root level. **Do not add application-wide CORS middleware** — FastMCP handles CORS for OAuth routes internally. Adding your own can create conflicts.

### FastMCP v2 vs v3 — stay on v2

v3.0.0 is still in beta. `AWSCognitoProvider` is available from **v2.12.4+** (and also in v3). The storage backend system (`py-key-value-aio`) is identical across both versions. Pin to `fastmcp<3` for production. Key v3 breaking changes include removal of auth provider environment variables and renaming `mount()` prefix to namespace — none are urgent.

---

## SPA hosting through the same CloudFront distribution eliminates CORS entirely

Configure CloudFront with two origins and path-based behaviors:

| Path pattern | Origin | Cache policy | Origin request policy |
|---|---|---|---|
| `/mcp/*` | Lambda Function URL | **CachingDisabled** | AllViewerExceptHostHeader |
| `/oauth/*` | Lambda Function URL | **CachingDisabled** | AllViewerExceptHostHeader |
| `/api/*` | Lambda Function URL | **CachingDisabled** | AllViewerExceptHostHeader |
| `*` (default) | S3 bucket (OAC) | CachingOptimized | — |

The default behavior serves the SPA from a **private S3 bucket with OAC** (not the legacy OAI, and not S3 static website hosting). Set the Default Root Object to `index.html`.

**SPA client-side routing fix:** When S3 receives a request for `/dashboard`, it returns 403 (no such object). The cleanest solution is a **CloudFront Function on the default behavior only**:

```javascript
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (!uri.match(/\.\w+$/)) {
    request.uri = '/index.html';
  }
  return request;
}
```

This costs $0.10 per million invocations and only affects the S3 behavior, not your API paths. Avoid using CloudFront custom error responses (403→index.html) because they're distribution-wide and would mask genuine API errors.

**Because SPA and API share the same CloudFront domain, CORS is not needed.** The browser treats all requests as same-origin. This eliminates preflight OPTIONS requests, CORS misconfiguration risks, and cookie scoping problems. This is the recommended AWS pattern for SPA + API architectures.

For deployment: `npm run build` → `aws s3 sync dist/ s3://BUCKET --delete` → `aws cloudfront create-invalidation --distribution-id ID --paths "/*"`. Set Vite's hashed assets (`/assets/main.abc123.js`) to long cache TTLs, but configure `index.html` with `Cache-Control: no-cache` in S3 metadata.

---

## Shield Standard is free, WAF is $6/month, but Lambda concurrency is the real safety net

**AWS Shield Standard** is automatically enabled at no charge on all CloudFront distributions. It protects against **Layer 3/4 DDoS attacks** (SYN/UDP floods, reflection attacks) but provides **zero Layer 7 (application-layer) protection** — no HTTP flood mitigation, no bot detection, no rate limiting. Shield Advanced at $3,000/month is absurd for a hobby project.

**CloudFront cannot rate-limit without WAF.** There is no built-in rate limiting, and CloudFront Functions are stateless — they can't count requests per IP over time. The CloudFront console's "one-click rate limiting" creates WAF rules behind the scenes. WAF pricing: **$5.00/month per Web ACL + $1.00/month per rule + $0.60 per million requests**. The cheapest useful WAF config (1 ACL + 1 rate-based rule) costs **~$6.06/month** — more than your entire infrastructure. Skip WAF initially unless the flat-rate Free plan's bundled 5 WAF rules provide sufficient coverage.

**Lambda reserved concurrency is your primary cost protection** and it's free to configure. Set `reserved_concurrent_executions` to **10** for a hobby project. Worst-case calculation if all 10 slots are saturated for one hour:

- 10 × 3,600s × 1 GB = 36,000 GB-seconds × $0.0000166667 = **$0.60/hour**
- Sustained for a full month (theoretical): ~$443 — extreme but bounded
- Realistic bad scenario (4 hours of abuse): **~$2.40**

Excess requests receive 429 (throttled) at zero cost. Combined with CloudFront caching for static assets (which never hit Lambda), the attack surface is limited to API/MCP paths only.

**Minimum viable protection stack for launch:**
- Shield Standard (free, automatic) — L3/L4 DDoS
- Lambda reserved concurrency at 10 (free) — hard cost ceiling
- Private S3 with OAC (free) — no direct bucket access
- CloudFront geographic restrictions (free) — limit to EU/US if applicable
- AWS Budget alert at $5 and $20 thresholds (free) — early warning
- CloudWatch alarm on Lambda `Throttles` metric > 0 (free tier covers basic monitoring)

---

## Total monthly bill breakdown and the traps that could inflate it

| Service | Normal usage (~100 MAU) | Notes |
|---|---|---|
| **Lambda** | $0.00 | 26,500 GB-s well within 400K GB-s free tier |
| **CloudFront** | $0.00 | 62K requests, ~3 GB within 10M/1 TB free tier |
| **S3** | ~$0.03 | Storage + PUT/GET requests; minimal |
| **Route 53** | $0.50 | Hosted zone; Alias queries to CloudFront are free |
| **DynamoDB** | ~$0.00 | ~200 operations/month rounds to zero |
| **Cognito** | $0.00 | 100 MAU within 10,000 free tier |
| **ACM** | $0.00 | Public certificates are free |
| **CloudWatch** | ~$0.01 | Basic metrics + ~2.5 MB logs |
| **Total** | **~$0.54/month** | $0.03 with flat-rate Free plan (Route 53 bundled) |

The flat-rate Free plan reduces this to roughly **$0.03/month** by bundling Route 53 and adding 5 WAF rules, but limits you to 1M requests and 100 GB (versus 10M and 1 TB on pay-as-you-go). The flat-rate plan also **does not support Lambda@Edge** or custom origin request/response header policies — verify that the managed `AllViewerExceptHostHeader` policy works before committing.

### Cost traps that actually matter

**Docker cold starts are billed as of August 2025.** AWS now charges for the INIT phase. Docker-based Lambda cold starts run 600ms–5s depending on image size. At a 20% cold start rate with 2,500 invocations, this adds ~1,500 GB-seconds (~$0.025) — negligible, but it stacks with CloudFront timeout pressure. A keep-warm CloudWatch Events ping every 5 minutes costs ~$0.50/month and prevents most cold starts. Provisioned concurrency ($3–5/month) is overkill for this stage.

**CloudFront does not retry POST requests**, so MCP calls won't trigger duplicate Lambda invocations. However, it retries GET/HEAD up to 3 times — set connection attempts to 1 for the Lambda behavior if you serve any GET endpoints.

**SSE streaming through CloudFront works** (set Lambda Function URL to `RESPONSE_STREAM` invoke mode) but adds **~500–800ms latency to TTFB** compared to direct Function URL access. For the streaming origin response timeout, CloudFront checks per-packet timing, so long-running streams work as long as data keeps flowing within the timeout window.

**S3 to CloudFront data transfer is free.** Lambda to S3 within the same region (eu-central-1) is also free. Cross-region transfers cost $0.01–0.02/GB — keep all services in eu-central-1, with the sole exception of the ACM certificate in us-east-1 (required for CloudFront, and free).

**Bot/crawler worst case:** If a bot bypasses CloudFront cache and hits Lambda directly with 1M requests × 2s average, that's 2M GB-seconds = **$33.33** — the Lambda concurrency limit of 10 makes this scenario physically impossible at scale (max ~14,400 invocations/hour with 1-second durations).

---

## Conclusion: a clear implementation sequence

The entire Level 2 + Level 3 stack is viable at **under $1/month** with aggressive free tier usage. Three non-obvious findings change the implementation approach:

**First, the CloudFront origin timeout is the single highest-risk configuration.** File the quota increase request to 180 seconds before deploying any TTS functionality behind CloudFront. The 60-second console maximum is too tight when cold starts compound with long executions.

**Second, the flat-rate Free plan is purpose-built for this use case** — it bundles Route 53, WAF (5 rules), S3 credits, and DDoS protection at $0/month. The trade-off is lower request limits (1M vs 10M) and no Lambda@Edge support. For a hobby project with ~62K monthly requests, the limits are generous. Start here and fall back to pay-as-you-go if you hit feature restrictions.

**Third, FastMCP's `AWSCognitoProvider` + DynamoDB + `stateless_http=True` is the correct architecture**, not a custom OAuth implementation. The provider handles DCR, PKCE proxying, and JWT issuance — attempting to build this from scratch would take weeks. The py-key-value DynamoDB backend is less documented than Redis but eliminates infrastructure management on Lambda. Pin to FastMCP v2 (`fastmcp<3`) and install `py-key-value-aio[dynamodb]`.

Implementation order: (1) Create CloudFront distribution with S3 origin for SPA + Lambda Function URL origin with increased timeout; (2) Add Route 53 hosted zone + ACM certificate in us-east-1; (3) Configure path-based behaviors with CachingDisabled for API paths; (4) Add CloudFront Function for SPA routing; (5) Create Cognito User Pool (Lite tier) with Resource Server matching `base_url/mcp`; (6) Create DynamoDB table for OAuth state with TTL enabled; (7) Configure `AWSCognitoProvider` with DynamoDB storage in FastMCP; (8) Mount FastMCP into FastAPI for REST endpoints; (9) Set Lambda reserved concurrency to 10 and configure budget alerts.