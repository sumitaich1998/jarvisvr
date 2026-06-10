# JarvisVR voice-service
# Referenced by infra/docker-compose as service "voice-service" at this exact path.
FROM python:3.11-slim AS base

# Audio + ML runtime libs (kept minimal; engines themselves are optional extras):
#   libportaudio2 -> sounddevice (mic/speaker)
#   libsndfile1   -> wav/soundfile handling
#   ffmpeg        -> faster-whisper audio decode
#   espeak-ng     -> pyttsx3 / piper phonemization on Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
        libportaudio2 \
        libsndfile1 \
        ffmpeg \
        espeak-ng \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Default bridge target inside the compose network.
    JARVIS_BACKEND_URL=ws://agent-backend:8765/jarvis \
    JARVIS_LOG_LEVEL=INFO

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml requirements.txt README.md ./
COPY jarvis_voice ./jarvis_voice

# Build arg lets infra opt into real engines, e.g. --build-arg EXTRAS="[recommended]".
# Default install is the light base so the image is small and always runnable.
ARG EXTRAS=""
RUN pip install --upgrade pip && pip install ".${EXTRAS}"

# Sanity-check the install at build time using the offline fallbacks.
RUN jarvis-voice selftest

# Liveness: selftest exercises wake/STT/TTS factories + a mock pipeline turn.
HEALTHCHECK --interval=30s --timeout=20s --start-period=10s --retries=3 \
    CMD ["jarvis-voice", "selftest"]

# Run as the voice front-end that bridges mic/STT/TTS to the agent-backend.
CMD ["jarvis-voice", "bridge"]
