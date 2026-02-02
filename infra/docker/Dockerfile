FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm

# Lambda Web Adapter (LWA) - /opt/extensions are run by Lambda automatically
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir ".[aws]"

CMD ["sh", "-c", "exec uvicorn ankify.mcp.ankify_mcp_server:app --host 0.0.0.0 --port $PORT"]