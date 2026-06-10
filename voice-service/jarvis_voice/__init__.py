"""JarvisVR voice-service — wake word + STT + TTS pipeline.

Gives Jarvis ears and a mouth. Three pluggable stages (wake word, STT, TTS),
each with a real engine option and an offline/mock fallback, so the whole thing
runs headless with zero external services.

Public surface is import-safe: heavy/optional engine imports are deferred into
the concrete implementations, so ``import jarvis_voice`` never fails on a machine
without models, GPUs, or audio devices.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .config import Config  # noqa: E402

__all__ = ["Config", "__version__"]
