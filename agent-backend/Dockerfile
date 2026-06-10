# JarvisVR agent-backend ("the brain").
# infra/docker-compose.yml references this image as service `agent-backend`
# exposing port 8765 (path /jarvis).
FROM python:3.11-slim

# Avoid .pyc files and force unbuffered stdout for clean container logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching. Copy the package metadata
# and source, then install the project itself.
COPY pyproject.toml README.md ./
COPY jarvis_backend ./jarvis_backend

RUN pip install .

# Runtime defaults (override via compose env / .env).
ENV JARVIS_HOST=0.0.0.0 \
    JARVIS_PORT=8765 \
    JARVIS_WS_PATH=/jarvis \
    JARVIS_LLM=mock \
    JARVIS_DATA_DIR=/data \
    # In the compose network holo-tools is mounted/served here; falls back to the
    # built-in catalog if the file is absent.
    JARVIS_HOLO_REGISTRY=/holo-tools/registry.json

# Persist long-term memory (notes/reminders) across restarts when mounted.
VOLUME ["/data"]

EXPOSE 8765

CMD ["python", "-m", "jarvis_backend"]
