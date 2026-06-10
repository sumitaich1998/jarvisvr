# JarvisVR mock brain.
#
# IMPORTANT: build with the *repo root* as context so we can pull in the shared
# protocol binding (see docker-compose.mock.yml):
#
#   docker build -f infra/mock-backend/Dockerfile -t jarvisvr/mock-backend .
#
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JARVIS_HOST=0.0.0.0 \
    JARVIS_PORT=8765 \
    JARVIS_WS_PATH=/jarvis \
    JARVIS_PROTOCOL_SCHEMA_DIR=/app/shared-protocol/schema

WORKDIR /app

# 1) Install the shared protocol binding (schemas stay at the path above).
COPY shared-protocol/ /app/shared-protocol/
RUN pip install /app/shared-protocol/python

# 2) Install mock deps, then copy the server.
COPY infra/mock-backend/requirements.txt /app/mock-backend/requirements.txt
RUN pip install -r /app/mock-backend/requirements.txt
COPY infra/mock-backend/ /app/mock-backend/

EXPOSE 8765

CMD ["python", "/app/mock-backend/server.py"]
