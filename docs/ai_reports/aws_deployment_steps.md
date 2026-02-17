# Ankify Deployment Plan: Level 2 + Level 3

Joint instructions for Alex and Claude Code. Each step marks who does what.

**Starting point:** Level 1 is live — Lambda + Function URL + S3, deployed via CDK.
**End state:** CloudFront + custom domain + HTTPS + Cognito OAuth, all under $1/month.

---

## Prerequisites & One-Time Setup

### P1. Register a domain name *(Alex, manual)*

Register at **Cloudflare Registrar** (~$10–11/year for .com) — cheaper than Route 53's $13–14/year. You'll point nameservers to Route 53 in step L2.3.

Decide on the domain structure now — this affects several configs downstream:

- Root domain: `ankify.dev` (or similar)
- MCP endpoint: `ankify.dev/mcp` (same domain, path-based routing)
- SPA: `ankify.dev/` (default behavior)

### P2. Request CloudFront origin response timeout increase *(Alex, AWS console)*

This is the **highest-risk blocker** — do it first because approval may take days.

// See: https://repost.aws/knowledge-center/cloudfront-custom-origin-response
// this won't work:

1. Go to **Service Quotas** → Amazon CloudFront → "Response timeout per origin"
2. Click "Request increase at account level"
3. Request **180 seconds**
4. Justification: "MCP server generates text-to-speech audio for language learning flashcards. TTS synthesis takes 30-60 seconds, plus Docker cold starts of 2-5 seconds. Need 120-180s origin response timeout."

Until approved, you can use **120 seconds** (configurable in console without approval). The plan uses 120s as default with a note to bump it.

### P3. Generate secrets for Level 3 *(Claude Code, bash)*

These are needed later but good to prepare now:

```bash
# JWT signing key for FastMCP's AWSCognitoProvider
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Fernet encryption key for OAuth token storage  
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Origin verify secret for CloudFront → Lambda auth
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store these securely (password manager). They'll go into Secrets Manager in step L3.4.

---

## Level 2: CloudFront + Custom Domain + HTTPS

### L2.1. Create ACM certificate in us-east-1 *(Alex, AWS console)*

**Must be us-east-1** — CloudFront only accepts certificates from this region, regardless of where Lambda runs.

1. Switch to **US East (N. Virginia)** in the console
2. ACM → Request public certificate
3. Domain name: `ankify.dev` (+ optionally `*.ankify.dev` as SAN)
4. Validation method: **DNS validation**
5. ACM gives you a CNAME record — you'll add it to Route 53 in step L2.3
6. Note the **certificate ARN** — needed for CDK

> **Cost:** $0.00 (ACM public certificates are free with CloudFront)
> **Auto-renewal:** ACM renews automatically 60 days before expiry as long as the DNS validation CNAME exists. Never delete it.

### L2.2. Create Route 53 hosted zone *(CDK)*

Add to the CDK stack. Route 53 is the one fixed cost at $0.50/month.

```python
from aws_cdk import aws_route53 as route53

hosted_zone = route53.HostedZone(
    self, "AnkifyHostedZone",
    zone_name="ankify.dev",
)

CfnOutput(self, "NameServers",
    value=Fn.join(", ", hosted_zone.hosted_zone_name_servers),
    description="Point your registrar's nameservers to these",
)
```

After deploy: copy the 4 NS records and **update your domain registrar** (Cloudflare) to use these nameservers. DNS propagation takes up to 48 hours.

If the ACM certificate from L2.1 is still pending, add the validation CNAME via Route 53 console (or `aws_certificatemanager.DnsValidatedCertificate` in CDK, though manual is fine for a one-time action).

### L2.3. Reference ACM certificate in CDK *(CDK)*

Since the cert is in us-east-1 and the stack is in eu-central-1, use `from_certificate_arn`:

```python
from aws_cdk import aws_certificatemanager as acm

certificate = acm.Certificate.from_certificate_arn(
    self, "AnkifyCert",
    certificate_arn="arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID",
)
```

Pass the ARN via CDK context so it's not hardcoded:

```python
cert_arn = self.node.try_get_context("certificate_arn")
certificate = acm.Certificate.from_certificate_arn(self, "AnkifyCert", cert_arn)
```

Deploy with: `cdk deploy -c certificate_arn=arn:aws:acm:us-east-1:...`

### L2.4. Switch Lambda Function URL to NONE auth + add origin secret *(CDK)*

We use the **secret header approach** rather than OAC. Rationale: MCP is POST-heavy, and OAC requires clients to compute `x-amz-content-sha256` for POST bodies — an unnecessary friction point. The secret header is injected by CloudFront and validated in Lambda code.

**CDK changes:**

```python
# Change Function URL auth from NONE to... keep it NONE  
# (it was already NONE in Level 1 — the secret header provides the auth)
function_url = lambda_fn.add_function_url(
    auth_type=lambda_.FunctionUrlAuthType.NONE,
    invoke_mode=lambda_.InvokeMode.BUFFERED,
)
```

Add the origin secret to the Lambda environment:

```python
origin_secret = secretsmanager.Secret.from_secret_name_v2(
    self, "OriginVerifySecret",
    secret_name="ankify/origin-verify",
)

# Add to lambda environment
"ANKIFY_ORIGIN_SECRET_ARN": origin_secret.secret_arn,

# Grant read access
origin_secret.grant_read(lambda_fn)
```

**Before deploying**, create the secret manually (one-time):

```bash
aws secretsmanager create-secret \
  --name "ankify/origin-verify" \
  --secret-string "YOUR_GENERATED_ORIGIN_SECRET" \
  --region eu-central-1
```

### L2.5. Add origin secret validation to Lambda code *(Claude Code)*

Add a middleware/check in the MCP server. Two options:

**Option A — Starlette middleware (recommended, catches all routes):**

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class OriginVerifyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, secret: str, exempt_paths: set[str] = None):
        super().__init__(app)
        self.secret = secret
        self.exempt_paths = exempt_paths or set()

    async def dispatch(self, request, call_next):
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        if request.headers.get("x-origin-verify") != self.secret:
            return Response("Forbidden", status_code=403)
        return await call_next(request)
```

**Option B — FastMCP custom_route won't work** (it doesn't wrap all routes). The middleware approach is correct.

Apply it only in Lambda (not local dev):

```python
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    origin_secret = _get_secret("ANKIFY_ORIGIN_SECRET_ARN")
    if origin_secret:
        app.add_middleware(
            OriginVerifyMiddleware,
            secret=origin_secret,
            exempt_paths={"/health"},  # LWA needs unauthenticated health checks
        )
```

### L2.6. Create CloudFront distribution *(CDK)*

This is the core of Level 2. Add to the stack:

```python
from aws_cdk import (
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_route53 as route53,
    aws_route53_targets as targets,
)

domain_name = "ankify.dev"

# Lambda Function URL origin with secret header
lambda_origin = origins.FunctionUrlOrigin(
    function_url,
    custom_headers={"x-origin-verify": "{{resolve:secretsmanager:ankify/origin-verify}}"},
    read_timeout=Duration.seconds(120),  # Bump to 180 after quota approval
    keepalive_timeout=Duration.seconds(60),
)

distribution = cloudfront.Distribution(
    self, "AnkifyDistribution",
    default_behavior=cloudfront.BehaviorOptions(
        origin=lambda_origin,
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
        cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
        origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
    ),
    domain_names=[domain_name],
    certificate=certificate,
    minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
    http_version=cloudfront.HttpVersion.HTTP2_AND_3,
)
```

**Key configuration choices:**

- `CachePolicy.CACHING_DISABLED` — MCP requests are unique, no caching benefit
- `ALL_VIEWER_EXCEPT_HOST_HEADER` — prevents the 403 Host mismatch error
- `ALLOW_ALL` — MCP uses POST
- `read_timeout=120s` — increase to 180 after quota approval in P2

> ⚠️ **CloudFront dynamic references (`{{resolve:...}}`) for custom headers**: Check if CDK supports this. If not, pass the secret value via CDK context or hardcode it (less ideal). Alternative: read from environment in the CDK app.

> ⚠️ **FunctionUrlOrigin** is a CDK L2 construct — verify it supports `custom_headers`. If not, use `HttpOrigin` with the Function URL domain:

```python
# Fallback if FunctionUrlOrigin doesn't support custom_headers
lambda_origin = origins.HttpOrigin(
    Fn.select(2, Fn.split("/", function_url.url)),  # extract domain from URL
    custom_headers={"x-origin-verify": origin_secret_value},
    read_timeout=Duration.seconds(120),
)
```

### L2.7. Add Route 53 alias record *(CDK)*

```python
route53.ARecord(
    self, "AnkifyAliasRecord",
    zone=hosted_zone,
    record_name=domain_name,
    target=route53.RecordTarget.from_alias(
        targets.CloudFrontTarget(distribution)
    ),
)
```

### L2.9. Add CloudWatch budget alarm *(Alex, AWS console or CDK)*

Quick console setup (one-time):

1. AWS Budgets → Create budget → Cost budget
2. Monthly budget: **$5.00**
3. Alert at 80% ($4.00) and 100% ($5.00) — email notification

Or in CDK:

```python
from aws_cdk import aws_budgets as budgets

budgets.CfnBudget(self, "AnkifyBudget",
    budget=budgets.CfnBudget.BudgetDataProperty(
        budget_type="COST",
        time_unit="MONTHLY",
        budget_limit=budgets.CfnBudget.SpendProperty(amount=5, unit="USD"),
    ),
    notifications_with_subscribers=[
        budgets.CfnBudget.NotificationWithSubscribersProperty(
            notification=budgets.CfnBudget.NotificationProperty(
                comparison_operator="GREATER_THAN",
                notification_type="ACTUAL",
                threshold=80,
            ),
            subscribers=[budgets.CfnBudget.SubscriberProperty(
                address="your@email.com",
                subscription_type="EMAIL",
            )],
        ),
    ],
)
```

### L2.10. Deploy and verify Level 2 *(Claude Code / Alex)*

```bash
cdk deploy -c certificate_arn=arn:aws:acm:us-east-1:... -c azure_region=westeurope
```

**Verification checklist:**

1. `curl https://ankify.dev/health` → `{"status": "healthy"}`
2. `curl -X POST https://ankify.dev/mcp` → should reach MCP server (401 or MCP response)
3. Direct Lambda URL without secret header → should return 403
4. Direct Lambda URL with correct header → should work (for debugging only)
5. Check CloudWatch logs for any timeout issues
6. Test a real deck generation through the MCP endpoint (the slow TTS path)

**If you get 504 Gateway Timeout:** The origin response timeout (L2.6) is too low. Increase `read_timeout` or check the P2 quota increase status.

**If you get 403:** Likely the Host header issue — confirm `ALL_VIEWER_EXCEPT_HOST_HEADER` is applied. Or the origin secret mismatch.

### L2.11. (Optional) SPA hosting preparation *(future)*

When you build a web frontend, add an S3 origin to the same distribution:

```python
spa_bucket = s3.Bucket(self, "AnkifySPABucket",
    removal_policy=RemovalPolicy.DESTROY,
    auto_delete_objects=True,
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
)

# S3 origin with OAC (standard for static assets)
s3_origin = origins.S3BucketV2Origin(spa_bucket)

# Override the default behavior to serve SPA from S3
# Add MCP/API as additional behaviors pointing to Lambda
```

Plus a CloudFront Function for SPA client-side routing:

```javascript
function handler(event) {
  var request = event.request;
  if (!request.uri.match(/\.\w+$/)) {
    request.uri = '/index.html';
  }
  return request;
}
```

This is **deferred** — not needed until you have a frontend. The current setup routes everything to Lambda.

---

## Level 3: Cognito Authentication

### L3.1. Create Cognito User Pool *(Alex, AWS console)*

Do this in the console — it's a one-time setup with many UI-driven options.

1. **Region:** `eu-central-1` (same as your Lambda)
2. **Cognito Console** → User pools → Create user pool
3. **Application type:** "Traditional web application"
4. **Name:** "Ankify MCP Server"
5. **Sign-in identifiers:** Email (simplest)
6. **Required attributes:** Email only
7. **Callback URL:** `https://ankify.dev/auth/callback`
8. **Tier:** Switch to **Lite** (not Essentials) — you only need basic auth + social login

After creation, note:

- **User Pool ID:** `eu-central-1_XXXXXXXXX`
- **App Client ID:** found in Applications → App clients → your app
- **App Client Secret:** same location

### L3.2. Configure Cognito OAuth settings *(Alex, AWS console)*

In the app client settings:

1. **Allowed callback URLs:**
   - `https://ankify.dev/auth/callback` (production)
   - `http://localhost:8000/auth/callback` (local development)
2. **OAuth 2.0 grant types:** Authorization code grant ✅
3. **OpenID Connect scopes:** `openid`, `email`, `profile`
4. **Cognito domain:** Set up under Branding → Domain → e.g., `ankify` → produces `ankify.auth.eu-central-1.amazoncognito.com`

### L3.3. Create Cognito Resource Server *(Alex, AWS console)*

**Critical** — without this, token exchange fails with `invalid_grant`.

1. In Cognito console: Branding → Resource servers → Create
2. **Resource server name:** "Ankify MCP"
3. **Resource server identifier:** `https://ankify.dev/mcp`*(Must exactly match `base_url` + MCP path)*
4. **Custom scopes:** (optional, can add later)
   - `generate_deck` — "Generate Anki flashcard decks"
   - `list_voices` — "List available TTS voices"

### L3.4. Store auth secrets in Secrets Manager *(Alex, bash)*

```bash
# Cognito client secret
aws secretsmanager create-secret \
  --name "ankify/cognito-client-secret" \
  --secret-string "YOUR_COGNITO_CLIENT_SECRET" \
  --region eu-central-1

# JWT signing key (generated in P3)
aws secretsmanager create-secret \
  --name "ankify/jwt-signing-key" \
  --secret-string "YOUR_JWT_SIGNING_KEY" \
  --region eu-central-1

# Fernet encryption key for OAuth token storage (generated in P3)
aws secretsmanager create-secret \
  --name "ankify/storage-encryption-key" \
  --secret-string "YOUR_FERNET_KEY" \
  --region eu-central-1
```

### L3.5. Create DynamoDB table for OAuth state *(CDK)*

```python
from aws_cdk import aws_dynamodb as dynamodb

oauth_table = dynamodb.TableV2(
    self, "AnkifyOAuthState",
    table_name="ankify-oauth-state",
    partition_key=dynamodb.Attribute(
        name="key", type=dynamodb.AttributeType.STRING
    ),
    billing=dynamodb.Billing.on_demand(),
    removal_policy=RemovalPolicy.DESTROY,
    time_to_live_attribute="ttl",  # auto-expire OAuth tokens
)

oauth_table.grant_read_write_data(lambda_fn)
```

> **Cost:** $1.25/million writes, $0.25/million reads, 25 GB free storage. At ~200 OAuth operations/month = **$0.00**.

### L3.6. Update CDK stack with new secrets and environment variables *(CDK)*

```python
# Reference secrets
cognito_client_secret = secretsmanager.Secret.from_secret_name_v2(
    self, "CognitoClientSecret", "ankify/cognito-client-secret")
jwt_signing_key = secretsmanager.Secret.from_secret_name_v2(
    self, "JwtSigningKey", "ankify/jwt-signing-key")
storage_encryption_key = secretsmanager.Secret.from_secret_name_v2(
    self, "StorageEncryptionKey", "ankify/storage-encryption-key")

# Grant read
for secret in [cognito_client_secret, jwt_signing_key, storage_encryption_key]:
    secret.grant_read(lambda_fn)

# Add to Lambda environment
# (Cognito User Pool ID and Client ID are not sensitive — can be plain env vars)
environment={
    # ... existing vars ...
    "ANKIFY_COGNITO_USER_POOL_ID": "eu-central-1_XXXXXXXXX",
    "ANKIFY_COGNITO_CLIENT_ID": "your-client-id",
    "ANKIFY_COGNITO_CLIENT_SECRET_ARN": cognito_client_secret.secret_arn,
    "ANKIFY_JWT_SIGNING_KEY_ARN": jwt_signing_key.secret_arn,
    "ANKIFY_STORAGE_ENCRYPTION_KEY_ARN": storage_encryption_key.secret_arn,
    "ANKIFY_OAUTH_TABLE_NAME": oauth_table.table_name,
    "ANKIFY_BASE_URL": f"https://{domain_name}",
}
```

Pass `domain_name`, User Pool ID, and Client ID via CDK context to avoid hardcoding.

### L3.7. Add auth dependencies to pyproject.toml *(Claude Code)*

```toml
[project.optional-dependencies]
aws = [
    # ... existing deps ...
    "py-key-value-aio[dynamodb]",
    "cryptography",
]
```

Pin FastMCP to v2: `"fastmcp>=2.12.4,<3"`

### L3.8. Update the MCP server code for auth *(Claude Code)*

This is the largest code change. The key architectural decision: **deploy FastMCP at root level (no mount prefix)** to avoid `.well-known` routing complexity.

```python
import os
from fastmcp import FastMCP
from fastmcp.server.auth.providers.aws import AWSCognitoProvider

def _get_secret(arn_env_var: str) -> str | None:
    """Fetch secret from Secrets Manager by ARN env var, or fall back to direct env."""
    arn = os.environ.get(arn_env_var)
    if arn:
        import boto3
        client = boto3.client("secretsmanager")
        return client.get_secret_value(SecretId=arn)["SecretString"]
    return None


def _build_auth_provider() -> AWSCognitoProvider | None:
    """Build Cognito auth provider if credentials are available."""
    user_pool_id = os.environ.get("ANKIFY_COGNITO_USER_POOL_ID")
    client_id = os.environ.get("ANKIFY_COGNITO_CLIENT_ID")
    base_url = os.environ.get("ANKIFY_BASE_URL")
  
    if not all([user_pool_id, client_id, base_url]):
        logger.info("Cognito auth not configured — running without auth")
        return None

    client_secret = _get_secret("ANKIFY_COGNITO_CLIENT_SECRET_ARN")
    jwt_signing_key = _get_secret("ANKIFY_JWT_SIGNING_KEY_ARN")
    encryption_key = _get_secret("ANKIFY_STORAGE_ENCRYPTION_KEY_ARN")
  
    # Build DynamoDB-backed encrypted storage
    from key_value.aio.stores.dynamodb import DynamoDBStore
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
    from cryptography.fernet import Fernet

    table_name = os.environ.get("ANKIFY_OAUTH_TABLE_NAME", "ankify-oauth-state")
    region = os.environ.get("AWS_REGION", "eu-central-1")
  
    dynamodb_store = DynamoDBStore(
        table_name=table_name,
        region_name=region,
    )
  
    client_storage = FernetEncryptionWrapper(
        key_value=dynamodb_store,
        fernet=Fernet(encryption_key),
    )

    return AWSCognitoProvider(
        user_pool_id=user_pool_id,
        aws_region=region,
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        jwt_signing_key=jwt_signing_key,
        client_storage=client_storage,
    )


# Build MCP server — with or without auth
auth_provider = _build_auth_provider()
mcp = FastMCP(
    name="Ankify",
    instructions="Create Anki decks with TTS speech from arbitrary input",
    auth=auth_provider,  # None = no auth (local dev), provider = protected
)
```

**Key design choices:**

- Auth is **optional** — `None` means no auth, so local `stdio` mode still works
- All secrets fetched from Secrets Manager at cold start (cached for container lifetime)
- DynamoDB store + Fernet encryption for OAuth state persistence across Lambda invocations
- `stateless_http=True` goes in the `http_app()` call (already there from Level 1)

### L3.9. Handle the health check exemption *(Claude Code)*

The health check (`/health`) must remain unauthenticated — Lambda Web Adapter pings it. FastMCP's `@mcp.custom_route` already bypasses OAuth auth, so the existing health check should work. Verify this during testing.

If it doesn't, the origin verify middleware from L2.5 already exempts `/health`. The OAuth layer should be tested separately.

### L3.10. Increase Lambda timeout *(CDK)*

Auth adds overhead: Cognito token validation, DynamoDB reads for OAuth state, plus the existing TTS workload. Increase timeout:

```python
timeout=Duration.minutes(2),  # up from 1 minute
```

The CloudFront origin response timeout (120s) is now the binding constraint, not Lambda.

### L3.11. Deploy and verify Level 3 *(Claude Code / Alex)*

```bash
cdk deploy \
  -c certificate_arn=arn:aws:acm:us-east-1:... \
  -c azure_region=westeurope \
  -c cognito_user_pool_id=eu-central-1_XXXXXXXXX \
  -c cognito_client_id=your-client-id \
  -c domain_name=ankify.dev
```

**Verification checklist:**

1. **Health check still works:**

   ```bash
   curl https://ankify.dev/health
   ```
2. **Unauthenticated MCP request returns 401:**

   ```bash
   curl -X POST https://ankify.dev/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"initialize","params":{}}'
   ```

   Expect: `401` with `WWW-Authenticate: Bearer resource_metadata="..."`
3. **OAuth discovery endpoints work:**

   ```bash
   curl https://ankify.dev/.well-known/oauth-protected-resource
   curl https://ankify.dev/.well-known/oauth-authorization-server
   ```

   Both should return JSON with correct URLs pointing to `ankify.dev`
4. **Dynamic Client Registration works:**

   ```bash
   curl -X POST https://ankify.dev/register \
     -H "Content-Type: application/json" \
     -d '{"client_name":"test","redirect_uris":["http://localhost:9999/callback"],"grant_types":["authorization_code"],"token_endpoint_auth_method":"none"}'
   ```

   Expect: JSON with `client_id`
5. **Full auth flow via browser:**

   - Open `https://ankify.dev/authorize?response_type=code&client_id=...&redirect_uri=...&code_challenge=...&code_challenge_method=S256&state=test123`
   - Should redirect to Cognito Hosted UI
   - After login → redirects back to your redirect_uri with `?code=...&state=test123`
6. **Test with a real MCP client:**

   - Add to Claude Desktop config:
     ```json
     {
       "mcpServers": {
         "ankify": {
           "url": "https://ankify.dev/mcp"
         }
       }
     }
     ```
   - Claude Desktop should trigger the OAuth flow, open browser for login, then connect successfully

---

## Complete CDK Stack Structure (Reference)

After both levels, the stack manages these resources:

| Resource                | CDK Construct                        | Notes                      |
| ----------------------- | ------------------------------------ | -------------------------- |
| S3 bucket (decks)       | `s3.Bucket`                        | 1-day expiry, existing     |
| Lambda function         | `lambda_.DockerImageFunction`      | ARM64, 333MB, 2min timeout |
| Function URL            | `lambda_fn.add_function_url`       | AUTH_NONE + secret header  |
| Azure TTS secret        | `secretsmanager.Secret` (ref)      | Existing                   |
| Origin verify secret    | `secretsmanager.Secret` (ref)      | New in L2                  |
| Cognito secrets (×3)   | `secretsmanager.Secret` (ref)      | New in L3                  |
| Route 53 hosted zone    | `route53.HostedZone`               | New in L2                  |
| ACM certificate         | `acm.Certificate` (ref, us-east-1) | New in L2                  |
| CloudFront distribution | `cloudfront.Distribution`          | New in L2                  |
| Route 53 A record       | `route53.ARecord` (alias)          | New in L2                  |
| DynamoDB table          | `dynamodb.TableV2`                 | New in L3                  |
| Budget alarm            | `budgets.CfnBudget`                | New in L2                  |

Secrets Manager resources are **referenced** (not created) by CDK — they're created manually via CLI because they contain sensitive values you don't want in CDK context or source control.

---

## Gotchas & Traps Checklist

- [ ] ACM certificate **must** be in us-east-1 (even though Lambda is in eu-central-1)
- [ ] Never forward the Host header to Lambda Function URLs → use `AllViewerExceptHostHeader`
- [ ] CloudFront **does not retry POST requests** — only GET/HEAD
- [ ] Cognito Resource Server identifier must **exactly match** `base_url/mcp` (e.g., `https://ankify.dev/mcp`)
- [ ] Cognito tier: use **Lite**, not Essentials — switch before adding users (10,000 MAU free on both, but Lite is cheaper after)
- [ ] Never enable Cognito Advanced Security Features on Lite — adds $0.05/MAU
- [ ] Use TOTP MFA (authenticator app), never SMS MFA ($0.01–0.04 per message)
- [ ] DNS validation CNAME for ACM: **never delete it** — needed for auto-renewal
- [ ] `stateless_http=True` is mandatory for Lambda (no server-side session state)
- [ ] Docker cold starts are billed (since Aug 2025) — ~$0.025/month at current volume, negligible
- [ ] Keep all services in eu-central-1 except ACM cert (us-east-1) — cross-region transfer costs money
- [ ] FastMCP: pin to `<3` — v3 has breaking changes and AWSCognitoProvider works on v2.12.4+
- [ ] DynamoDB TTL deletions are free — enable for automatic OAuth token cleanup
- [ ] CloudFront origin secret is in the CloudFormation template (not encrypted) — acceptable tradeoff vs OAC complexity for POST

---

## Monthly Cost at ~100 Users

| Service         | Cost                                                                |
| --------------- | ------------------------------------------------------------------- |
| Lambda          | $0.00 (free tier)                                                   |
| CloudFront      | $0.00 (free tier)                                                   |
| S3              | ~$0.03                                                              |
| Route 53        | $0.50                                                               |
| DynamoDB        | ~$0.00                                                              |
| Cognito         | $0.00 (free tier)                                                   |
| ACM             | $0.00                                                               |
| CloudWatch      | ~$0.01                                                              |
| Secrets Manager | ~$0.02 (5 secrets × $0.40/secret/month = $0.17, but partial month) |
| **Total** | **~$0.73/month**                                              |

Note: Secrets Manager is $0.40/secret/month — with 5 secrets that's $2.00/month at full price. Consider consolidating secrets into fewer JSON-structured secrets to reduce cost (e.g., one `ankify/auth-config` secret containing all auth values).
