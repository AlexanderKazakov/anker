# Deploying Ankify behind CloudFront: everything you need to know

You're a Python developer who built Ankify — a Lambda function in a Docker container that generates Anki flashcard decks with text-to-speech audio. You understand Lambda, Docker, and S3. Now you want to put CloudFront in front of your Lambda Function URL, add a custom domain with HTTPS, and lock things down properly. This guide explains every concept you'll encounter, from scratch, using Ankify as the running example throughout.

---

## 1. What CloudFront actually is (and why timeouts matter)

Before diving into configuration, you need a mental model of what CloudFront does. **CloudFront is a reverse proxy and CDN (Content Delivery Network) that sits between your users and your Lambda function.** When someone calls `ankify.yourdomain.com`, they're not talking to Lambda directly — they're talking to a CloudFront edge server (one of 400+ worldwide), which then forwards the request to your Lambda Function URL on their behalf.

CloudFront was originally built to cache and serve static files — images, CSS, JavaScript bundles — from edge locations close to users. A user in Tokyo gets your files from a server in Tokyo instead of waiting for a round-trip to your origin server in `us-east-1`. For static content, responses are nearly instant: CloudFront asks the origin for a file, gets it in milliseconds, caches it, and serves it to future requesters directly.

This "designed for static content" heritage explains why CloudFront's **default origin response timeout is 30 seconds**. For a typical web application returning HTML or JSON, 30 seconds is extraordinarily generous. Most API responses complete in under 1 second. The 30-second default is already a safety net, not a tight constraint — for normal web traffic.

But Ankify isn't normal web traffic. When a user requests a flashcard deck with TTS audio, your Lambda function might spend 30–60 seconds generating speech audio, building the deck, and uploading it to S3. And that's where the trouble starts.

### Origin response timeout: the clock that starts when CloudFront is waiting

The **origin response timeout** (also called "origin read timeout" in the API — same setting, different name) is the number of seconds CloudFront will wait for your origin to **start sending a response** after CloudFront forwards the request. It also applies between each packet of data during the response.

Think of it like ordering food at a restaurant. The origin response timeout is how long the waiter will wait at the kitchen window before assuming your order was lost. **The default is 30 seconds.** If your Lambda function takes 45 seconds to generate TTS audio before it can send any response back, CloudFront gives up at 30 seconds and returns a **504 Gateway Timeout** error to the user. Your Lambda function is still running — it doesn't know CloudFront walked away — but the user gets an error page.

For GET and HEAD requests, CloudFront will actually retry up to 3 times (configurable), each time waiting up to the timeout. For POST requests — which is what Ankify's MCP server likely uses — **CloudFront does not retry**. It drops the connection immediately after the timeout and returns the 504.

### Response completion timeout: the total wall-clock limit

The **response completion timeout** is a newer CloudFront feature that sets the **maximum total time** CloudFront will wait for a complete response, across all packets and retries. While the origin response timeout governs the gap between individual packets, the response completion timeout is the overall wall clock.

Analogy: the origin response timeout is "if I don't hear anything for 30 seconds, I'm leaving." The response completion timeout is "regardless of how the conversation is going, I'm leaving after 2 minutes total." By default, CloudFront does **not** enforce a response completion timeout — it's only the per-packet origin response timeout that applies.

### What you need to do for Ankify

Since your TTS operations take 30–60 seconds, the default 30-second origin response timeout will kill your requests. You need to increase it. Here's how:

**Up to 120 seconds:** Change the value directly in the CloudFront console (Distribution → Origins → Edit → Origin response timeout) or in your CloudFormation template's `CustomOriginConfig`. No approval needed.

**Up to 180 seconds:** Request an increase through the AWS Service Quotas dashboard. Navigate to Amazon CloudFront → "Response timeout per origin" → "Request increase at account level." This is self-service and typically approved quickly.

**Beyond 180 seconds:** Submit a quota increase request with a written justification explaining your use case. AWS reviews these manually.

For Ankify, setting the origin response timeout to **120 seconds** through the console or CloudFormation is probably sufficient and requires no approval process. If your TTS generation occasionally takes longer, request the 180-second quota increase as a safety margin. The important thing: **after any quota increase is approved, you must manually update your distribution's origin settings to use the new value.** The quota increase just raises the ceiling — it doesn't change your distribution automatically.

---

## 2. Why CloudFront still makes sense for a slow API

You might wonder: if CloudFront is designed for fast, cacheable static content, why use it for an API that takes 60 seconds to respond? Three reasons make CloudFront the pragmatic choice for Ankify.

**First, the alternatives are worse.** API Gateway — the "obvious" choice for putting an API in front of Lambda — historically had a **hard 29-second integration timeout** that could not be increased at all. AWS relaxed this in June 2024 for Regional REST APIs, but the increase requires a quota request and may reduce your throttle limits. HTTP APIs (API Gateway v2) may still face the old limit. CloudFront's 120-second ceiling (180+ with a quota bump) gives you more room out of the box.

**Second, CloudFront gives you a custom domain with free HTTPS.** You get `ankify.yourdomain.com` with a free TLS certificate, automatic certificate renewal, and global edge routing — all things you'd need to build separately otherwise.

**Third, you might actually benefit from caching.** If multiple users request the same flashcard deck, CloudFront can cache the response and serve it instantly to subsequent requesters. Even if caching doesn't apply to every request, it's a bonus when it does.

The mental model to internalize is this: **CloudFront is a configurable reverse proxy** that happens to also be a CDN. The caching layer is the "CDN" part. The proxying-to-your-origin part is just a reverse proxy, and the timeouts are configurable precisely because AWS recognized that not every origin is serving static files. You're using CloudFront as a reverse proxy with CDN benefits — and that's a perfectly legitimate use case.

### The timeout landscape across AWS services

Here's a concrete comparison so you can see where CloudFront fits:

| Service | Default timeout | Maximum timeout | Notes |
|---------|----------------|-----------------|-------|
| CloudFront (origin response) | 30s | 180s+ (with quota increase) | Configurable, no hard ceiling published |
| API Gateway (REST, Regional) | 29s | ~300s (with quota request, since June 2024) | May reduce throttle limits |
| API Gateway (HTTP API v2) | 29s | 29s | Hard limit, no override |
| Lambda Function URL (direct) | N/A | 15 minutes | No proxy timeout — client controls |
| Lambda execution | 3s default | 15 minutes | Configured on the function itself |

Calling your Lambda Function URL directly has no proxy timeout at all — the client just waits as long as it wants. But you lose custom domains, HTTPS certificates, caching, WAF integration, and access control. CloudFront gives you all of those, at the cost of a configurable timeout you need to be aware of.

---

## 3. Origin Access Control: locking the back door

### What "origin" means

In CloudFront terminology, the **origin** is the server where your actual content lives — the thing CloudFront forwards requests to. For Ankify, the origin is your Lambda Function URL (something like `abc123xyz.lambda-url.us-east-1.on.aws`). If you were serving a static website, the origin might be an S3 bucket. The origin is the "source of truth" that CloudFront proxies.

### The problem with an open origin

When you create a Lambda Function URL, it gets a public HTTPS endpoint. If that endpoint's `AuthType` is set to `NONE`, **anyone on the internet can call it directly**, bypassing CloudFront entirely. This creates several problems:

- Users can skip your CDN, hitting Lambda directly and missing any caching benefits
- Any WAF (Web Application Firewall) rules you attach to CloudFront are bypassed
- You can't enforce rate limiting or geographic restrictions
- You're paying for Lambda invocations that didn't go through your intended front door
- Someone could discover and abuse your Lambda URL directly

It's like having a store with a front entrance (CloudFront) where you check IDs and enforce rules, but leaving the loading dock (Lambda Function URL) unlocked so anyone can walk in the back.

### How OAC solves this

**Origin Access Control (OAC)** is CloudFront's mechanism for proving to your origin that a request genuinely came from your CloudFront distribution. When OAC is enabled, here's what happens step by step:

1. A user sends a request to `ankify.yourdomain.com`
2. CloudFront receives the request at an edge location
3. Before forwarding the request to your Lambda Function URL, **CloudFront cryptographically signs the request** using AWS Signature Version 4 (SigV4) — the same signing protocol that the AWS CLI uses when you run `aws` commands
4. CloudFront adds authentication headers (`Authorization`, `X-Amz-Date`, `X-Amz-Security-Token`) to the request
5. The signed request arrives at your Lambda Function URL
6. Lambda's auth layer verifies the signature. It checks: "Was this request signed by a principal that has permission to invoke me?" If yes, the request proceeds. If not, Lambda returns **403 Forbidden**

For this to work, you set your Lambda Function URL's `AuthType` to `AWS_IAM` (instead of `NONE`). This tells Lambda to require valid IAM signatures on every request. Then you add a **resource-based policy** to your Lambda function granting the CloudFront service principal (`cloudfront.amazonaws.com`) permission to invoke it, scoped to your specific distribution's ARN.

Now your Lambda Function URL is locked: direct calls without a valid CloudFront signature get rejected with 403. The back door is sealed.

### What the configuration values mean

In your CloudFormation template, you'll create an OAC resource like this:

```yaml
AnkifyOAC:
  Type: AWS::CloudFront::OriginAccessControl
  Properties:
    OriginAccessControlConfig:
      Name: AnkifyOAC
      OriginAccessControlOriginType: lambda
      SigningBehavior: always
      SigningProtocol: sigv4
```

**`SigningProtocol: sigv4`** means "use AWS Signature Version 4 to sign requests." This is currently the only option — there's no sigv3 or sigv5 alternative. You're just telling CloudFront which cryptographic signing method to use.

**`SigningBehavior: always`** means "sign every single request CloudFront sends to this origin, no exceptions." The alternative `no-override` would only sign requests that don't already have an `Authorization` header from the viewer, and `never` would disable signing entirely. For Ankify, **`always` is what you want** — every request to your Lambda must be authenticated.

You also need a Lambda permission allowing CloudFront to invoke your function:

```yaml
AnkifyCloudFrontPermission:
  Type: AWS::Lambda::Permission
  Properties:
    Action: lambda:InvokeFunctionUrl
    FunctionName: !Ref AnkifyFunction
    Principal: cloudfront.amazonaws.com
    SourceArn: !Sub 'arn:aws:cloudfront::${AWS::AccountId}:distribution/${AnkifyDistribution}'
```

The `SourceArn` condition ensures that only *your specific* CloudFront distribution can invoke this Lambda — not any random CloudFront distribution in any AWS account.

---

## 4. The Host header problem: why Lambda rejects forwarded requests

### A quick primer on HTTP headers

Every HTTP request includes **headers** — key-value pairs of metadata that travel alongside the request. You've seen these if you've ever used `requests` in Python:

```python
response = requests.get("https://ankify.yourdomain.com/generate", 
                         headers={"Content-Type": "application/json"})
```

Headers tell the server things like what content type the client accepts, what cookies it has, what authentication token it's carrying, and — critically — **what hostname it thinks it's talking to**.

### What the Host header does

The **Host header** tells the server which website the client wants to reach. When your browser visits `ankify.yourdomain.com`, it sends `Host: ankify.yourdomain.com` in the request. This matters because a single server (or IP address) can host many different websites, and the Host header is how the server knows which one you want.

### Why forwarding it causes 403 errors

Here's the problem. When a user visits `ankify.yourdomain.com`, their request includes `Host: ankify.yourdomain.com`. CloudFront receives this request. If CloudFront naively forwards this exact Host header to your Lambda Function URL, Lambda receives a request claiming to be for `ankify.yourdomain.com`. But Lambda Function URLs expect the Host header to match **their own domain** — something like `abc123xyz.lambda-url.us-east-1.on.aws`.

Lambda sees the mismatched Host header and rejects the request with **403 Forbidden**. It's a security measure: Lambda won't process requests that claim to be for a domain it doesn't recognize. When OAC is involved, the Host header is also part of the SigV4 signature calculation, so a mismatched Host header causes signature validation to fail too.

### The fix: AllViewerExceptHostHeader

AWS provides a **managed origin request policy** called `AllViewerExceptHostHeader` (policy ID: `b689b0a8-53d0-40ab-baf2-68738e2966ac`) that solves this exactly. An origin request policy controls which headers, cookies, and query strings CloudFront forwards to the origin.

This policy does exactly what its name says: it forwards **all viewer headers except the Host header** to the origin. When the viewer's Host header is stripped, CloudFront automatically substitutes the origin's own domain name as the Host header. So Lambda receives `Host: abc123xyz.lambda-url.us-east-1.on.aws` — which matches, and the request succeeds.

The policy also forwards all cookies and all query strings, so your Lambda function still receives everything it needs from the original request. Only the Host header is swapped.

In your CloudFormation template:

```yaml
DefaultCacheBehavior:
  OriginRequestPolicyId: b689b0a8-53d0-40ab-baf2-68738e2966ac
```

This single line prevents the 403 errors. AWS created this managed policy specifically for Lambda Function URL and API Gateway origins behind CloudFront — it's the officially recommended solution.

---

## 5. POST requests and the payload signing complication

### The signature needs to cover the body

When CloudFront signs a request with SigV4 for OAC, the signature covers the request headers, method, path, and query string. But for POST and PUT requests, there's also a **request body** — the JSON payload your MCP client sends to Ankify. Lambda's SigV4 validation wants to verify the body wasn't tampered with, and it does this using a header called **`x-amz-content-sha256`**.

This header contains the **SHA-256 hash of the request body**. It's a fingerprint: if someone changes even one byte of the body, the hash won't match, and Lambda rejects the request. The problem is that **CloudFront doesn't compute this hash for you**. CloudFront signs the headers but expects the client to provide the body hash.

### Why this is a problem for Ankify

Your MCP client sends POST requests to Ankify with JSON payloads describing what flashcards to generate. For OAC to work with these POST requests, the client would need to:

1. Compute the SHA-256 hash of the request body
2. Include it as an `x-amz-content-sha256` header

In Python, that looks like:

```python
import hashlib
body = b'{"deck": "Spanish Vocab", "cards": [...]}'
content_hash = hashlib.sha256(body).hexdigest()
headers = {"x-amz-content-sha256": content_hash}
```

This is awkward. You're asking every client to understand AWS request signing internals just to call your API. For a public-facing API, this is a significant usability problem. CloudFront Functions can't help because they don't have access to the request body. Lambda@Edge could compute the hash, but it truncates bodies larger than 1MB and adds complexity.

### The simpler alternative: a shared secret header

For many real-world deployments — especially ones like Ankify where the MCP protocol already handles its own authentication — there's a simpler pattern that avoids the POST signing issue entirely:

1. Set your Lambda Function URL's `AuthType` to `NONE` (publicly accessible)
2. Configure CloudFront to inject a **custom secret header** into every request it forwards to the origin
3. In your Lambda function code, check for that secret header and reject requests without it

In CloudFormation, you add the secret as a custom origin header:

```yaml
Origins:
  - Id: AnkifyOrigin
    DomainName: abc123xyz.lambda-url.us-east-1.on.aws
    CustomOriginConfig:
      OriginProtocolPolicy: https-only
    OriginCustomHeaders:
      - HeaderName: x-origin-verify
        HeaderValue: my-long-random-secret-value
```

In your Lambda function (Python):

```python
def handler(event, context):
    if event["headers"].get("x-origin-verify") != os.environ["ORIGIN_SECRET"]:
        return {"statusCode": 403, "body": "Forbidden"}
    # ... proceed with request
```

CloudFront always adds this header before forwarding to the origin. Users never see it — it's injected at the CloudFront layer. Anyone calling your Lambda Function URL directly won't have this header, so they get rejected.

### Trade-offs between OAC and the secret header approach

**OAC with `AWS_IAM`** is cryptographically stronger: it uses IAM-based authentication with rotating credentials. There's no secret to manage or rotate. However, it requires clients to compute `x-amz-content-sha256` for POST requests, which is a significant friction point.

**The secret header approach** is simpler and works transparently with POST requests — no client changes needed. The downside is it's "security by obscurity": the secret lives in your CloudFormation template, and the Lambda function is technically invocable by anyone (though requests without the secret header are rejected). You should rotate the secret periodically, perhaps using AWS Secrets Manager.

For Ankify — a Lambda-based MCP server that primarily handles POST requests — **the secret header approach is often the more practical choice**. It avoids the POST body signing complexity while still ensuring only CloudFront-routed traffic reaches your function.

---

## 6. TLS certificates and ACM: giving Ankify a real domain

### What TLS is and why you need a certificate

When you visit a website starting with `https://`, your browser and the server establish an **encrypted connection** using TLS (Transport Layer Security, the successor to SSL). This encryption prevents anyone between you and the server — your ISP, a coffee shop WiFi operator, a government — from reading or modifying the data in transit.

To establish this encrypted connection, the server needs a **TLS certificate** — a digital document that proves "I really am `ankify.yourdomain.com`." The certificate is issued by a **Certificate Authority (CA)**, a trusted third party that verified you control that domain. Your browser has a built-in list of trusted CAs and checks every certificate against that list. If the certificate is valid and matches the domain, the browser shows the padlock icon. If not, you get the scary "Your connection is not private" warning.

Without a certificate, you can't serve HTTPS traffic. And without HTTPS, modern browsers will warn users, many APIs won't connect, and your data travels in plaintext.

### What ACM does and why it's free

**AWS Certificate Manager (ACM)** is AWS's service for creating and managing TLS certificates. For Ankify, you'll use ACM to get a certificate for `ankify.yourdomain.com`.

**ACM public certificates are completely free** when used with AWS services like CloudFront, Application Load Balancers, or API Gateway. AWS absorbs the cost because free certificates drive adoption of their paid services — you need CloudFront or an ALB to actually use the certificate, and those services generate revenue. It also eliminates a common barrier to HTTPS adoption. You never handle the private key; ACM manages it securely.

The traditional alternative — buying a certificate from a commercial CA like DigiCert — costs $100–$300/year, requires manual renewal, and you have to manage private keys yourself. ACM eliminates all of that.

### Creating a certificate for ankify.yourdomain.com

Here's the concrete process:

**Step 1: Request the certificate in us-east-1.** Open ACM in the AWS console and make sure you're in the **US East (N. Virginia) / `us-east-1` region**. This is critical — CloudFront will only accept certificates from us-east-1. Request a public certificate and enter your domain: `ankify.yourdomain.com`.

**Step 2: Prove you own the domain.** ACM needs to verify you control `ankify.yourdomain.com` before issuing a certificate. Choose **DNS validation** (strongly recommended over email validation). ACM gives you a CNAME record to add to your DNS — something like `_abc123.ankify.yourdomain.com → _def456.acm-validations.aws`. If you use Route 53 for DNS, there's a one-click button to create this record automatically.

**Step 3: Wait for validation.** ACM periodically checks if the CNAME record exists. Once it finds it — usually within minutes — the certificate status changes from "Pending validation" to **"Issued."** The certificate is now ready to use.

**Step 4: Attach it to CloudFront.** In your CloudFront distribution configuration, add `ankify.yourdomain.com` as an **Alias** (alternate domain name), and reference the ACM certificate:

```yaml
DistributionConfig:
  Aliases:
    - ankify.yourdomain.com
  ViewerCertificate:
    AcmCertificateArn: arn:aws:acm:us-east-1:123456789:certificate/abc-def-ghi
    SslSupportMethod: sni-only
    MinimumProtocolVersion: TLSv1.2_2021
```

**Step 5: Point DNS to CloudFront.** Create a DNS record pointing `ankify.yourdomain.com` to your CloudFront distribution. With Route 53, use an **Alias record** (type A) pointing to the distribution's domain name. With other DNS providers, use a CNAME record pointing to `d111111abcdef8.cloudfront.net`.

### Why the certificate must live in us-east-1

This requirement confuses almost everyone the first time. Your Lambda function might be in `eu-west-1`. Your S3 bucket might be in `ap-southeast-1`. But **the ACM certificate for CloudFront must be in `us-east-1`**, period.

The reason is architectural: **CloudFront is a global service**, not a regional one. It runs on 400+ edge locations worldwide and doesn't "belong" to any single region. AWS chose `us-east-1` as the home region for CloudFront's control plane — the management layer that stores distribution configurations, certificates, and other global resources. When you attach a certificate to a CloudFront distribution, that certificate is **automatically distributed from us-east-1 to every edge location worldwide**. A user in Sydney and a user in London both get served with the same certificate, from their nearest edge location.

Other global AWS resources follow the same pattern: WAF WebACLs for CloudFront and Lambda@Edge functions must also be created in `us-east-1`.

### Auto-renewal: set it and forget it

ACM certificates are valid for **13 months**. Starting 60 days before expiration, ACM automatically attempts to renew the certificate. If you used DNS validation and the CNAME record is still in place (don't delete it!), renewal happens silently and automatically — same certificate ARN, no configuration changes needed, no downtime. You never have to think about it again.

This is a massive improvement over traditional certificate management, where expired certificates cause outages and emergency renewals at 2 AM. With ACM and DNS validation, **the CNAME record you created once is the only thing you need to maintain**.

### What sni-only means (and why you want it)

The `SslSupportMethod: sni-only` setting in the ViewerCertificate configuration refers to **Server Name Indication (SNI)** — a TLS extension that allows a single IP address to serve certificates for multiple domains. When a client connects to CloudFront and says "I want `ankify.yourdomain.com`," SNI lets CloudFront's edge server pick the right certificate from potentially thousands it hosts on the same IP.

The alternative, `vip` (dedicated IP), allocates dedicated IP addresses at every edge location for your certificate alone. It costs **$600/month** and exists only to support ancient clients (Windows XP-era browsers) that don't support SNI. Since virtually all modern clients support SNI, **`sni-only` is free and correct for Ankify** — and for nearly every deployment in 2026.

---

## Conclusion

Deploying Ankify behind CloudFront involves six interconnected concepts that form a coherent security and delivery architecture. **CloudFront's 30-second default timeout** exists because CDNs were built for fast static content; increase it to 120 seconds for your TTS workload, and you sidestep the 504 errors without needing a quota request. **OAC with SigV4 signing** locks your Lambda Function URL so only CloudFront can invoke it — though for POST-heavy APIs, the simpler custom secret header pattern avoids the payload hashing complication entirely. **The AllViewerExceptHostHeader policy** is a one-line fix for the Host header mismatch that would otherwise cause mysterious 403 errors. And **ACM in us-east-1** gives you a free, auto-renewing TLS certificate that CloudFront distributes globally.

The key insight tying these pieces together: CloudFront is not just a CDN. It's a globally distributed reverse proxy that happens to cache things. Once you see it that way, every configuration decision — timeouts, access control, header policies, certificates — follows logically from the question: "How do I configure this proxy to correctly and securely forward requests to my Lambda function?"