# AWS App Runner: Simpler, but Not Free

**Summary:** App Runner is a good architectural fit for Ankify's polling-heavy MCP workload. It solves the concurrency and complexity issues of Lambda+CloudFront. However, its timeout advantage over CloudFront is modest (not dramatic), and the minimum cost is **~$2.50–4/month**. The service can be **paused** when not in use to avoid charges entirely.

---

## 1. Why App Runner Fits Ankify Better than Lambda

| Feature                 | Lambda (Current)                                                                                                                                     | App Runner (Proposed)                                                                                                   | Verdict                                                             |
| :---------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------ |
| **Server Model**  | **Per-Request Isolation.** <br />Every concurrent request spins up a new instance. <br />No shared event loop.                                 | **Persistent Server.** <br />One Uvicorn process handles multiple <br />concurrent requests via async event loop. | **App Runner** <br />(Correct architecture for polling/async) |
| **Timeouts**      | **15 mins** (Lambda and FunctionUrl), <br />but ~120-180**s** limit if behind CloudFront <br />(need to configure, default is just 30s). | **~120s** (internal load balancer idle timeout). <br />No CloudFront required.                                    | **Comparable.** Both adequate for 30–60s TTS.                |
| **Cold Starts**   | **Yes.** 2-5s latency on new instances (Docker).                                                                                               | **Minimal.** ~100-500ms CPU allocation delay <br />when waking from idle (CPU throttled, memory active).          | **App Runner** (Sub-second vs. multi-second)                  |
| **Custom Domain** | **Hard.** Requires CloudFront + ACM + Route53 manual wiring.                                                                                   | **Easy.** Built-in wizard handles certs & DNS automatically.                                                      | **App Runner** (10x simpler setup)                            |
| **Cost**          | **\$0.00** (Free Tier).                                                                                                                        | **~\$2.50–4/month** (running). <br />**\$0** if paused.                                                    | **Lambda** (Winner if budget is strictly \$0)                 |

### Concurrency

**Lambda limitation:** Lambda cannot handle concurrent requests on a single instance. 100 polling clients = 100 Lambda instances (huge overhead).
**App Runner advantage:** A single App Runner instance (1 vCPU) can handle **100+ concurrent polling requests** easily because Uvicorn uses `asyncio` to handle them efficiently. It behaves exactly like a normal server.

### Storage Persistence

App Runner containers have an ephemeral local filesystem like Lambda, but with a key difference: App Runner containers are **long-lived** (hours/days), so in-memory caches and local file caches persist across requests on the same instance. Lambda instances may be recycled after minutes of inactivity. Despite this, we must still rely on DynamoDB for `AWSCognitoProvider` persistence (OAuth state), since App Runner instances can be replaced during scaling events or deployments.

---

## 2. Pricing & "Scale to Zero"

**Claim:** "App Runner scales to zero."
**Fact Check:** **PARTIALLY TRUE.**
A *running* App Runner service does **not** scale below one "Provisioned Instance." However, App Runner supports **`PauseService`** / **`ResumeService`** API operations. A paused service has **zero running instances** and costs **$0.00/month** for compute. Resume takes ~30 seconds to a few minutes. For a hobby project with sporadic usage, this can be automated via a CloudWatch/cron rule to pause when idle.

**Cost Breakdown (eu-central-1, while running):**

1. **Provisioned Instance:** You pay for memory *all the time*, and CPU only when *active*.
   * Cheapest Config: 0.25 vCPU / 0.5 GB RAM.
   * Provisioned Cost: $0.007 / GB-hour = **~ 24 × 30 × 0.007 = $5.04 / GB-month**.
   * For 0.5 GB: **~$2.52/month** (memory only, while idle).
   * Active container instance cost: $0.064 / vCPU-hour, billed per second.
   * Active containers scale up if concurrency (configurable, default 100, max 200) per container is exceeded.
   * Containers are scaled down to 1 provisioned (and 0 active) instance if not used.
2. **Automatic Deployment (optional):** AWS charges **$1.00/month** per service for automatic deployment from a GitHub/Bitbucket source code connection. **Not needed if deploying via ECR container images** (which is the recommended approach since we already have a Dockerfile and CDK).
3. **Total Minimum Cost (running):** ~$2.50/month (idle, 0.5 GB provisioned) + a couple of dollars per vCPU-hour if used lightly. **$0/month if paused.**

*Source: [AWS App Runner Pricing](https://aws.amazon.com/apprunner/pricing/)*

---

## 3. Authentication (Cognito)

**No native integration like API Gateway.**
App Runner does **not** have a built-in "Authorizer" that sits in front of your app to block requests, like API Gateway does.

**Solution:** You must handle authentication **inside your application code**, exactly the same way it works with FastMCP on Lambda Function URL — FastMCP `AWSCognitoProvider` middleware checks the header.

---

## 4. Timeouts

**Adequate for TTS, but not unlimited.**

App Runner does **not** expose a configurable request timeout parameter. The effective timeout is governed by App Runner's **internal reverse proxy/load balancer**, which has an **idle timeout of ~120 seconds**. This means:

* **Effective Timeout:** ~120 seconds between data packets. As long as data keeps flowing (e.g., SSE streaming), connections can stay open longer.
* **Not Configurable:** Unlike CloudFront (where you can request a quota increase to 180s), App Runner's internal timeout is fixed.
* **Adequate for Ankify:** Our TTS operations take 30–60 seconds, well within the ~120s window. This is comparable to CloudFront's 120–180s configurable timeout — **not a dramatic improvement.**
* **Not suitable** for workloads requiring multi-minute single-request durations without streaming.

Source: [AWS App Runner Development](https://docs.aws.amazon.com/apprunner/latest/dg/develop.html#:~:text=There%20is%20a%20total%20of,the%20applications%20that%20you%20use.)

---

## 5. Deployment Plan (Migration from Lambda)

Switching is straightforward because your code (FastMCP) is standard Python and already Dockerized.

1. **Docker Image via ECR (Recommended):**
   * Your existing `Dockerfile` works as-is.
   * Push the image to Amazon ECR (already done via CDK).
   * App Runner pulls the image from ECR — no build step needed on App Runner's side.
   * This avoids the $1/month GitHub connection fee and gives full control over the build process.
2. **Service Creation:**
   * Go to App Runner Console (or use CDK/CloudFormation).
   * Source: **Container Registry → Amazon ECR** (select the image).
   * Instance Configuration: 0.25 vCPU / 0.5 GB (minimum).
   * Port: 8080 (App Runner default).
3. **Env Vars:** Copy your `.env` variables (COGNITO_*, AZURE_*, etc.) into the App Runner service configuration.
4. **Custom Domain:** Use the "Custom Domains" tab to link `ankify.dev`. App Runner handles certificate provisioning automatically; you just need to add the provided CNAME records to your DNS.
