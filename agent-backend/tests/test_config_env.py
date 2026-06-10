"""Config: env-var parsing, path resolution, and helper properties."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_backend import config as cfg_mod
from jarvis_backend.config import Config, _env_bool, _env_int, _first_existing

_ALL_VARS = [
    "JARVIS_HOST", "JARVIS_PORT", "JARVIS_WS_PATH", "JARVIS_LLM", "JARVIS_OPENAI_MODEL",
    "JARVIS_ANTHROPIC_MODEL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "JARVIS_MODEL",
    "JARVIS_LLM_BASE_URL", "JARVIS_BASE_URL", "JARVIS_LLM_API_KEY", "JARVIS_USE_LITELLM",
    "JARVIS_VISION", "JARVIS_WEATHER_API_KEY", "OPENWEATHER_API_KEY", "JARVIS_HOLO_REGISTRY",
    "JARVIS_DATA_DIR", "JARVIS_ENV_FILE", "JARVIS_SKILLS_DIR", "JARVIS_MAX_STEPS",
    "JARVIS_PERCEPTION", "JARVIS_PROACTIVE", "JARVIS_VISION_FPS", "JARVIS_VISION_BUFFER",
    "JARVIS_SETTINGS_VALIDATE", "JARVIS_ORCHESTRATION", "JARVIS_TRACE", "JARVIS_LOG_LEVEL",
    "JARVIS_LOG_JSON",
]


@pytest.fixture
def clean_env(monkeypatch):
    for v in _ALL_VARS:
        monkeypatch.delenv(v, raising=False)
    return monkeypatch


# --- primitive helpers ------------------------------------------------------


def test_env_bool_truthy_and_falsey(monkeypatch):
    for truthy in ("1", "true", "YES", "On"):
        monkeypatch.setenv("X_BOOL", truthy)
        assert _env_bool("X_BOOL", False) is True
    for falsey in ("0", "no", "off", "nope"):
        monkeypatch.setenv("X_BOOL", falsey)
        assert _env_bool("X_BOOL", True) is False
    monkeypatch.delenv("X_BOOL", raising=False)
    assert _env_bool("X_BOOL", True) is True  # default when unset


def test_env_int_valid_invalid_empty(monkeypatch):
    monkeypatch.setenv("X_INT", "42")
    assert _env_int("X_INT", 7) == 42
    monkeypatch.setenv("X_INT", "not-a-number")
    assert _env_int("X_INT", 7) == 7
    monkeypatch.setenv("X_INT", "   ")
    assert _env_int("X_INT", 7) == 7
    monkeypatch.delenv("X_INT", raising=False)
    assert _env_int("X_INT", 7) == 7


def test_first_existing(tmp_path):
    f = tmp_path / "exists.json"
    f.write_text("{}")
    assert _first_existing(tmp_path / "nope.json", f) == f
    assert _first_existing(tmp_path / "a", tmp_path / "b") is None


# --- from_env ---------------------------------------------------------------


def test_from_env_defaults(clean_env):
    c = Config.from_env(load_env_file=False)
    assert c.host == "0.0.0.0"
    assert c.port == 8765
    assert c.ws_path == "/jarvis"
    assert c.llm_provider == "mock"
    assert c.perception_enabled is True
    assert c.orchestration_enabled is True
    assert c.trace_enabled is True
    assert c.log_level == "INFO"


def test_from_env_full_override(clean_env):
    m = clean_env
    m.setenv("JARVIS_HOST", "127.0.0.1")
    m.setenv("JARVIS_PORT", "9000")
    m.setenv("JARVIS_WS_PATH", "/x")
    m.setenv("JARVIS_LLM", "  OpenAI ")  # stripped + lowercased
    m.setenv("JARVIS_MODEL", "custom-model")
    m.setenv("JARVIS_BASE_URL", "http://fallback/v1")  # JARVIS_BASE_URL fallback
    m.setenv("JARVIS_LLM_API_KEY", "gk")
    m.setenv("JARVIS_USE_LITELLM", "1")
    m.setenv("JARVIS_VISION", "OpenAI")
    m.setenv("OPENWEATHER_API_KEY", "owm")  # weather fallback var
    m.setenv("JARVIS_MAX_STEPS", "9")
    m.setenv("JARVIS_PERCEPTION", "0")
    m.setenv("JARVIS_PROACTIVE", "1")
    m.setenv("JARVIS_VISION_FPS", "5")
    m.setenv("JARVIS_VISION_BUFFER", "3")
    m.setenv("JARVIS_SETTINGS_VALIDATE", "1")
    m.setenv("JARVIS_ORCHESTRATION", "0")
    m.setenv("JARVIS_TRACE", "0")
    m.setenv("JARVIS_LOG_LEVEL", "debug")
    m.setenv("JARVIS_LOG_JSON", "1")
    c = Config.from_env(load_env_file=False)
    assert c.host == "127.0.0.1" and c.port == 9000 and c.ws_path == "/x"
    assert c.llm_provider == "openai"
    assert c.llm_model == "custom-model"
    assert c.llm_base_url == "http://fallback/v1"
    assert c.llm_api_key == "gk"
    assert c.use_litellm is True
    assert c.vision_provider == "openai"
    assert c.weather_api_key == "owm"
    assert c.max_tool_steps == 9
    assert c.perception_enabled is False
    assert c.proactive is True
    assert c.vision_default_fps == 5 and c.vision_buffer_frames == 3
    assert c.settings_validate is True
    assert c.orchestration_enabled is False
    assert c.trace_enabled is False
    assert c.log_level == "DEBUG" and c.log_json is True


def test_registry_path_absolute_and_relative(clean_env, tmp_path):
    abs_reg = tmp_path / "registry.json"
    clean_env.setenv("JARVIS_HOLO_REGISTRY", str(abs_reg))
    assert Config.from_env(load_env_file=False).holo_registry_path == abs_reg
    clean_env.setenv("JARVIS_HOLO_REGISTRY", "holo-tools/registry.json")
    rel = Config.from_env(load_env_file=False).holo_registry_path
    assert rel.is_absolute() and rel.name == "registry.json"


def test_data_dir_and_skills_dir_relative(clean_env):
    clean_env.setenv("JARVIS_DATA_DIR", "mydata")
    clean_env.setenv("JARVIS_SKILLS_DIR", "myskills")
    c = Config.from_env(load_env_file=False)
    assert c.data_dir.is_absolute() and c.data_dir.name == "mydata"
    assert c.skills_dir.is_absolute() and c.skills_dir.name == "myskills"


def test_data_dir_and_skills_dir_absolute(clean_env, tmp_path):
    clean_env.setenv("JARVIS_DATA_DIR", str(tmp_path / "d"))
    clean_env.setenv("JARVIS_SKILLS_DIR", str(tmp_path / "s"))
    c = Config.from_env(load_env_file=False)
    assert c.data_dir == tmp_path / "d"
    assert c.skills_dir == tmp_path / "s"


def test_env_file_var(clean_env, tmp_path):
    clean_env.setenv("JARVIS_ENV_FILE", str(tmp_path / "custom.env"))
    c = Config.from_env(load_env_file=False)
    assert c.env_file == tmp_path / "custom.env"
    assert c.env_path == tmp_path / "custom.env"


# --- helper properties ------------------------------------------------------


def test_memory_and_user_agents_files(tmp_path):
    c = Config(data_dir=tmp_path)
    assert c.memory_file == tmp_path / "memory.json"
    assert c.user_agents_file == tmp_path / "user_agents.json"


def test_env_path_default():
    assert Config(env_file=None).env_path.name == ".env"


def test_tools_json_path(tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text("{}")
    assert Config(holo_registry_path=reg).tools_json_path is None  # no sibling tools.json
    (tmp_path / "tools.json").write_text("{}")
    assert Config(holo_registry_path=reg).tools_json_path == tmp_path / "tools.json"
    assert Config(holo_registry_path=None).tools_json_path is None


def test_model_label_mock_and_resolved():
    assert Config(llm_provider="mock").model_label() == "mock"
    assert Config(llm_provider="openai", llm_model="gpt-4o").model_label() == "gpt-4o"


def test_model_label_exception_fallback(monkeypatch):
    def boom(_):
        raise RuntimeError("resolve failed")

    monkeypatch.setattr(cfg_mod, "Config", Config)
    monkeypatch.setattr("jarvis_backend.providers.resolve", boom)
    assert Config(llm_provider="openai").model_label() == "openai"


def test_summary_contains_key_fields(tmp_path):
    s = Config(data_dir=tmp_path, holo_registry_path=None).summary()
    assert "llm=mock" in s and "orchestration=True" in s and "<fallback>" in s
    s2 = Config(data_dir=tmp_path, holo_registry_path=tmp_path / "registry.json").summary()
    assert "registry.json" in s2
