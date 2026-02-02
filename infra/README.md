# AWS Deployment for Ankify MCP Server

This folder contains AWS CDK infrastructure code to deploy the Ankify MCP Server as a Lambda function with a public Function URL.

## Architecture

```
                                    ┌─────────────────┐
                                    │   S3 Bucket     │
                                    │ (Anki decks)    │
                                    └────────▲────────┘
                                             │
┌──────────┐     ┌─────────────────┐    ┌────┴────┐
│  Client  │────▶│  Function URL   │───▶│ Lambda  │
└──────────┘     │ (public HTTPS)  │    │ (ARM64) │
                 └─────────────────┘    └─────────┘
```

- **Lambda**: Runs the MCP server via Lambda Web Adapter (streams responses)
- **S3**: Stores generated `.apkg` files with 1-day auto-expiration
- **Function URL**: Public HTTPS endpoint (no API Gateway needed)

## Prerequisites

1. **AWS CLI** configured with credentials

   ```bash
   aws configure
   # or use environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
   ```
2. **Node.js 18+** (required for CDK CLI)

   ```bash
   node --version  # should be 18.x or higher
   ```
3. **AWS CDK CLI**

   ```bash
   npm install -g aws-cdk
   cdk --version
   ```
4. **Docker** (for building the Lambda container image)

   ```bash
   docker --version
   ```

## Setup

### 1. Create a separate virtual environment for CDK

The CDK has different dependencies than the main Ankify project. Create a dedicated venv:

```bash
cd infra/cdk

# Create and activate venv
uv venv --python 3.12

# Install CDK dependencies
uv pip install -r requirements.txt

# Activate the env
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows
```

### 2. Bootstrap CDK (first time only)

CDK needs to create some resources in your AWS account before first deployment:

```bash
cdk bootstrap
```

### 3. Fix the Python import path

The CDK app uses relative imports. Set `PYTHONPATH` before running CDK commands:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

Or add this to your shell profile for convenience.

## Deployment

### Deploy with default settings

Uses your AWS CLI's configured account/region:

```bash
cd infra/cdk
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

cdk deploy
```

### Deploy with explicit account/region

```bash
cdk deploy -c account=123456789012 -c region=eu-west-1
```

### Deploy with Azure TTS credentials

The Lambda needs Azure credentials for text-to-speech, stored in AWS Secrets Manager.

**Create the secret:**

```bash
aws secretsmanager create-secret \
    --name "ankify/azure-tts" \
    --secret-string "YOUR_AZURE_SUBSCRIPTION_KEY"
```

**Delete the secret (if needed):**

```bash
aws secretsmanager delete-secret --secret-id "ankify/azure-tts"
# Add --force-delete-without-recovery to skip the 7-day recovery window
```

**Deploy with custom Azure region:**

```bash
cdk deploy -c azure_region=westeurope
```

### View changes before deploying

```bash
cdk diff
```

## Configuration via cdk.json

Copy the example file and fill in your values:

```bash
cp cdk.json.example cdk.json
```

Then edit `cdk.json` with your AWS account ID and other settings (regions).

**Note:** Azure TTS credentials are stored in AWS Secrets Manager (see above), not in cdk.json.

## After Deployment

CDK outputs the Function URL:

```
Outputs:
AnkifyStack.FunctionUrl = https://xxxxxxxxxx.lambda-url.eu-west-1.on.aws/
AnkifyStack.BucketName = ankifystack-ankifydecksbucketxxxxx-xxxxx
```

Test the health endpoint:

```bash
curl https://xxxxxxxxxx.lambda-url.eu-west-1.on.aws/health
```

## Cleanup

Remove all deployed resources:

```bash
cdk destroy
```

## Troubleshooting

### "No module named 'stacks'" error

Set `PYTHONPATH`:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### CDK synth fails with account/region errors

Either:

1. Configure AWS CLI: `aws configure`
2. Pass explicitly: `cdk deploy -c account=... -c region=...`
3. Set environment variables: `AWS_DEFAULT_ACCOUNT`, `AWS_DEFAULT_REGION`

### Docker build fails

Ensure Docker is running:

```bash
docker ps  # should not error
```

### Docker build fails with "exec format error" on x86_64

When building the ARM64 Lambda image on an x86_64 machine, you may see:

```
exec /bin/sh: exec format error
```

This happens because Docker cannot execute ARM64 binaries natively on x86_64. You need to register QEMU as a binary interpreter with your kernel:

```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

This registers `binfmt_misc` handlers so the kernel automatically uses QEMU to emulate ARM64 binaries. See: [multiarch/qemu-user-static](https://github.com/multiarch/qemu-user-static)

**Note:** This registration persists in memory until reboot. You'll need to re-run it after each system restart.

**For GitHub Actions:** Use `docker/setup-qemu-action@v3` before CDK build.

### Lambda timeout or memory errors

Adjust in `stacks/ankify_stack.py`:

```python
memory_size=2048,  # increase if needed
timeout=Duration.minutes(15),  # max is 15 min
```
