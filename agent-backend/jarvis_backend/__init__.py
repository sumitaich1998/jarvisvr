"""JarvisVR agent-backend — the LLM agent 'brain'.

A Python WebSocket server that hosts an LLM agent loop with tool-calling,
planning, and memory. It is the protocol endpoint the Quest 3 ``unity-client``
connects to (see ``docs/PROTOCOL.md``). It runs fully offline via a deterministic
mock LLM so the whole JarvisVR stack is demoable with no API keys.
"""

from .protocol import PROTOCOL_VERSION

__version__ = "0.1.0"

__all__ = ["__version__", "PROTOCOL_VERSION"]
