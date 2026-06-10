"""Environment-driven configuration for the agent-backend.

All settings have safe defaults so the server boots with zero configuration and
runs fully offline (mock LLM, fallback widget catalog).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Repo root: <repo>/agent-backend/jarvis_backend/config.py -> parents[2].
_PACKAGE_DIR = Path(__file__).resolve().parent
_AGENT_BACKEND_DIR = _PACKAGE_DIR.parent
_REPO_ROOT = _AGENT_BACKEND_DIR.parent


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _first_existing(*candidates: Path) -> Optional[Path]:
    for c in candidates:
        if c and c.is_file():
            return c
    return None


@dataclass
class Config:
    """Resolved runtime configuration."""

    host: str = "0.0.0.0"
    port: int = 8765
    ws_path: str = "/jarvis"

    llm_provider: str = "mock"  # mock | openai | anthropic | gemini | groq | … (see providers.py)
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-latest"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Universal multi-provider settings (resolved via providers.py registry).
    llm_model: Optional[str] = None  # JARVIS_MODEL — generic model override
    llm_base_url: Optional[str] = None  # JARVIS_LLM_BASE_URL — custom/local/OpenAI-compat
    llm_api_key: Optional[str] = None  # JARVIS_LLM_API_KEY — generic key fallback
    use_litellm: bool = False  # JARVIS_USE_LITELLM — force the LiteLLM universal adapter

    # v1.1 vision: which provider "sees" frames. mock = deterministic offline.
    vision_provider: str = "mock"  # mock | openai | anthropic

    weather_api_key: Optional[str] = None

    # Widget catalog published by holo-tools/. May be absent (fallback is used).
    holo_registry_path: Optional[Path] = None

    data_dir: Path = field(default_factory=lambda: _AGENT_BACKEND_DIR / ".data")

    # Where runtime settings (provider/model/API key) are persisted (chmod 600).
    env_file: Optional[Path] = None

    max_tool_steps: int = 6

    # v1.1 perception toggles.
    perception_enabled: bool = True
    proactive: bool = False  # proactive observations on notable sounds (opt-in)
    vision_default_fps: int = 2
    vision_buffer_frames: int = 8

    # v1.1 settings (§5.15): best-effort live key validation on settings_update.
    settings_validate: bool = False  # off by default (offline-safe)

    # v1.2 multi-agent orchestration (§9).
    orchestration_enabled: bool = True  # JARVIS_ORCHESTRATION
    skills_dir: Optional[Path] = None  # JARVIS_SKILLS_DIR (default <repo>/skills)

    # v1.3 tracing + authoring (§10).
    trace_enabled: bool = True  # JARVIS_TRACE (record per-turn traces; streaming gated by subscribe)

    log_level: str = "INFO"
    log_json: bool = False

    @classmethod
    def from_env(cls, *, load_env_file: bool = True) -> "Config":
        if load_env_file:
            # Load <agent-backend>/.env then process env (process env wins).
            load_dotenv(_AGENT_BACKEND_DIR / ".env", override=False)
            load_dotenv(override=False)

        registry_env = os.getenv("JARVIS_HOLO_REGISTRY")
        if registry_env:
            registry_path: Optional[Path] = Path(registry_env).expanduser()
            if not registry_path.is_absolute():
                # Resolve relative paths against the repo root for stability.
                registry_path = (_REPO_ROOT / registry_path).resolve()
        else:
            registry_path = _first_existing(
                _REPO_ROOT / "holo-tools" / "registry.json",
                Path.cwd() / "holo-tools" / "registry.json",
            )

        data_dir_env = os.getenv("JARVIS_DATA_DIR")
        if data_dir_env:
            data_dir = Path(data_dir_env).expanduser()
            if not data_dir.is_absolute():
                data_dir = (_AGENT_BACKEND_DIR / data_dir).resolve()
        else:
            data_dir = _AGENT_BACKEND_DIR / ".data"

        env_file_env = os.getenv("JARVIS_ENV_FILE")
        env_file = Path(env_file_env).expanduser() if env_file_env else None

        skills_env = os.getenv("JARVIS_SKILLS_DIR")
        if skills_env:
            skills_dir = Path(skills_env).expanduser()
            if not skills_dir.is_absolute():
                skills_dir = (_REPO_ROOT / skills_dir).resolve()
        else:
            skills_dir = _REPO_ROOT / "skills"

        return cls(
            host=os.getenv("JARVIS_HOST", "0.0.0.0"),
            port=_env_int("JARVIS_PORT", 8765),
            ws_path=os.getenv("JARVIS_WS_PATH", "/jarvis"),
            llm_provider=os.getenv("JARVIS_LLM", "mock").strip().lower(),
            openai_model=os.getenv("JARVIS_OPENAI_MODEL", "gpt-4o-mini"),
            anthropic_model=os.getenv(
                "JARVIS_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            llm_model=os.getenv("JARVIS_MODEL") or None,
            llm_base_url=(
                os.getenv("JARVIS_LLM_BASE_URL")
                or os.getenv("JARVIS_BASE_URL")
                or None
            ),
            llm_api_key=os.getenv("JARVIS_LLM_API_KEY") or None,
            use_litellm=_env_bool("JARVIS_USE_LITELLM", False),
            vision_provider=os.getenv("JARVIS_VISION", "mock").strip().lower(),
            weather_api_key=(
                os.getenv("JARVIS_WEATHER_API_KEY")
                or os.getenv("OPENWEATHER_API_KEY")
                or None
            ),
            holo_registry_path=registry_path,
            data_dir=data_dir,
            env_file=env_file,
            max_tool_steps=_env_int("JARVIS_MAX_STEPS", 6),
            perception_enabled=_env_bool("JARVIS_PERCEPTION", True),
            proactive=_env_bool("JARVIS_PROACTIVE", False),
            vision_default_fps=_env_int("JARVIS_VISION_FPS", 2),
            vision_buffer_frames=_env_int("JARVIS_VISION_BUFFER", 8),
            settings_validate=_env_bool("JARVIS_SETTINGS_VALIDATE", False),
            orchestration_enabled=_env_bool("JARVIS_ORCHESTRATION", True),
            skills_dir=skills_dir,
            trace_enabled=_env_bool("JARVIS_TRACE", True),
            log_level=os.getenv("JARVIS_LOG_LEVEL", "INFO").upper(),
            log_json=_env_bool("JARVIS_LOG_JSON", False),
        )

    # -- helpers ------------------------------------------------------------

    @property
    def memory_file(self) -> Path:
        return self.data_dir / "memory.json"

    @property
    def user_agents_file(self) -> Path:
        """Persisted user-authored agent roster (§10.2)."""
        return self.data_dir / "user_agents.json"

    @property
    def env_path(self) -> Path:
        """The .env file runtime settings persist to (default <agent-backend>/.env)."""
        return self.env_file if self.env_file is not None else _AGENT_BACKEND_DIR / ".env"

    @property
    def tools_json_path(self) -> Optional[Path]:
        """holo-tools/tools.json next to the registry, if present."""
        if self.holo_registry_path:
            candidate = self.holo_registry_path.parent / "tools.json"
            if candidate.is_file():
                return candidate
        return None

    def model_label(self) -> str:
        """Human-facing model label for logs (resolved across all providers)."""
        try:
            from .providers import resolve

            return resolve(self).model
        except Exception:  # noqa: BLE001 - never let logging break startup
            return self.llm_provider or "mock"

    def summary(self) -> str:
        reg = str(self.holo_registry_path) if self.holo_registry_path else "<fallback>"
        return (
            f"host={self.host} port={self.port} path={self.ws_path} "
            f"llm={self.llm_provider} model={self.model_label()} "
            f"vision={self.vision_provider} perception={self.perception_enabled} "
            f"proactive={self.proactive} orchestration={self.orchestration_enabled} "
            f"skills_dir={self.skills_dir} registry={reg} data_dir={self.data_dir}"
        )


__all__ = ["Config"]
