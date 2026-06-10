"""Setup wizard: interactive branches, provider selection, validation."""

from __future__ import annotations

import jarvis_backend.agent.llm as llm_mod
from jarvis_backend import providers as P
from jarvis_backend import setup_wizard as W
from jarvis_backend.agent.llm import LLMProvider, LLMResult, MockLLM


def test_model_and_key_env_var():
    assert W.model_env_var("openai") == "JARVIS_OPENAI_MODEL"
    assert W.model_env_var("anthropic") == "JARVIS_ANTHROPIC_MODEL"
    assert W.model_env_var("groq") == "JARVIS_GROQ_MODEL"
    assert W.key_env_var(P.get_provider("openai")) == "OPENAI_API_KEY"
    assert W.key_env_var(P.get_provider("custom")) == "JARVIS_LLM_API_KEY"


def test_select_provider():
    provs = P.all_providers()
    assert W._select_provider("", provs).id == "mock"
    assert W._select_provider("2", provs) is provs[1]
    assert W._select_provider("999", provs) is None
    assert W._select_provider("openai", provs).id == "openai"
    assert W._select_provider("bogus", provs) is None


def test_format_value_quoting():
    assert W._format_value("plain") == "plain"
    assert W._format_value("has space") == '"has space"'
    assert W._format_value('a"b') == '"a\\"b"'
    assert W._format_value("") == '""'


# --- interactive flows ------------------------------------------------------


def test_interactive_needs_base_url(tmp_path):
    env = tmp_path / ".env"
    inputs = iter(["ollama", "", ""])  # provider, model(default), base_url(default)
    res = W.run_setup(
        env_path=env, input_fn=lambda p="": next(inputs),
        getpass_fn=lambda p="": "", print_fn=lambda s: None, env={},
    )
    assert res.provider_id == "ollama"
    assert "JARVIS_OLLAMA_BASE_URL" in env.read_text()


def test_interactive_requires_key_but_none_entered(tmp_path):
    env = tmp_path / ".env"
    printed = []
    inputs = iter(["openai", ""])  # provider, model
    W.run_setup(
        env_path=env, input_fn=lambda p="": next(inputs),
        getpass_fn=lambda p="": "", print_fn=printed.append, env={},
    )
    assert any("No key entered" in p for p in printed)


def test_interactive_validate_yes(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr(W, "validate_provider", lambda info, **k: (True, "OK"))
    inputs = iter(["openai", "", "y"])  # provider, model, validate? yes
    res = W.run_setup(
        env_path=env, input_fn=lambda p="": next(inputs),
        getpass_fn=lambda p="": "sk-key", print_fn=lambda s: None, env={},
    )
    assert res.validated is True


def test_interactive_validate_fails_but_continues(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    printed = []
    monkeypatch.setattr(W, "validate_provider", lambda info, **k: (False, "401"))
    inputs = iter(["openai", "", "y"])
    res = W.run_setup(
        env_path=env, input_fn=lambda p="": next(inputs),
        getpass_fn=lambda p="": "sk-key", print_fn=printed.append, env={},
    )
    assert res.validated is False
    assert any("could not validate" in p for p in printed)


def test_interactive_unknown_provider_defaults_mock(tmp_path):
    env = tmp_path / ".env"
    printed = []
    res = W.run_setup(
        env_path=env, input_fn=lambda p="": "nonsense",
        getpass_fn=lambda p="": "", print_fn=printed.append, env={},
    )
    assert res.provider_id == "mock"
    assert any("Unknown provider" in p for p in printed)


# --- validate_provider (sync) -----------------------------------------------


class _FakeLLM(LLMProvider):
    name = "openai"

    def __init__(self, *, fail=False):
        self._fail = fail

    async def complete(self, messages, tools, *, images=None):
        if self._fail:
            raise RuntimeError("auth failed")
        return LLMResult(content="pong")


def test_validate_provider_fell_back_to_mock(monkeypatch):
    monkeypatch.setattr(llm_mod, "create_llm", lambda cfg: MockLLM())
    ok, msg = W.validate_provider(P.get_provider("openai"), model="gpt-4o", base_url=None, api_key="k")
    assert ok is False and "fell back" in msg


def test_validate_provider_ok(monkeypatch):
    monkeypatch.setattr(llm_mod, "create_llm", lambda cfg: _FakeLLM())
    ok, msg = W.validate_provider(P.get_provider("openai"), model="gpt-4o", base_url=None, api_key="k")
    assert ok is True and msg == "OK"


def test_validate_provider_call_fails(monkeypatch):
    monkeypatch.setattr(llm_mod, "create_llm", lambda cfg: _FakeLLM(fail=True))
    ok, msg = W.validate_provider(P.get_provider("openai"), model="gpt-4o", base_url=None, api_key="k")
    assert ok is False and "RuntimeError" in msg


def test_validate_provider_build_error(monkeypatch):
    def boom(cfg):
        raise RuntimeError("cannot build")

    monkeypatch.setattr(llm_mod, "create_llm", boom)
    ok, msg = W.validate_provider(P.get_provider("openai"), model="m", base_url=None, api_key="k")
    assert ok is False and "could not build" in msg


# --- non-interactive extras -------------------------------------------------


def test_non_interactive_validate(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "validate_provider", lambda info, **k: (True, "OK"))
    res = W.run_setup(
        env_path=tmp_path / ".env", provider="openai", api_key="sk-1",
        non_interactive=True, do_validate=True, print_fn=lambda s: None, env={},
    )
    assert res.validated is True


def test_non_interactive_key_from_env(tmp_path):
    res = W.run_setup(
        env_path=tmp_path / ".env", provider="openai", non_interactive=True,
        print_fn=lambda s: None, env={"OPENAI_API_KEY": "sk-env"},
    )
    assert "OPENAI_API_KEY=sk-env" in (tmp_path / ".env").read_text()
    assert res.provider_id == "openai"
