"""settings_service: validation, base_url handling, validation, hot-swap, no leak."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from jarvis_backend import settings_service as S
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from tests.conftest import make_config


@pytest.fixture(autouse=True)
def _restore_env():
    snap = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snap)


def _agent(tmp_path) -> Agent:
    return Agent.build(make_config(tmp_path), MockLLM())


def _apply(agent, payload, tmp_path, **kw):
    return S.apply_settings_update(agent, payload, env_path=tmp_path / ".env", **kw)


# --- build_server_settings --------------------------------------------------


def test_build_server_settings_no_key_leak(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    out = S.build_server_settings(make_config(tmp_path, llm_provider="openai"))
    import json

    assert "sk-secret" not in json.dumps(out)
    openai_entry = next(p for p in out["llm"]["providers"] if p["id"] == "openai")
    assert openai_entry["key_set"] is True
    assert out["llm"]["current"]["provider"] == "openai"


# --- payload validation -----------------------------------------------------


def test_apply_rejects_non_dict_payload(tmp_path):
    with pytest.raises(S.SettingsError) as e:
        _apply(_agent(tmp_path), "not a dict", tmp_path)
    assert e.value.code == "invalid_settings"


def test_apply_requires_llm_object(tmp_path):
    with pytest.raises(S.SettingsError) as e:
        _apply(_agent(tmp_path), {"llm": "x"}, tmp_path)
    assert e.value.code == "invalid_settings"


def test_apply_non_string_field(tmp_path):
    with pytest.raises(S.SettingsError) as e:
        _apply(_agent(tmp_path), {"llm": {"provider": 123}}, tmp_path)
    assert e.value.code == "invalid_settings"


def test_apply_unknown_provider(tmp_path):
    with pytest.raises(S.SettingsError) as e:
        _apply(_agent(tmp_path), {"llm": {"provider": "nope"}}, tmp_path)
    assert e.value.code == "provider_unavailable"


# --- base_url + model handling ----------------------------------------------


def test_apply_base_url_override_and_model_default(tmp_path):
    a = _agent(tmp_path)
    out = _apply(a, {"llm": {"provider": "custom", "base_url": "http://host/v1", "api_key": "k"}}, tmp_path)
    assert a.config.llm_base_url == "http://host/v1"
    assert a.config.llm_provider == "custom"
    # switching provider without a model uses the registry default
    out2 = _apply(a, {"llm": {"provider": "openai"}}, tmp_path)
    assert a.config.llm_model == "gpt-4o-mini"
    assert out2["llm"]["current"]["provider"] == "openai"


def test_apply_falls_back_to_mock_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JARVIS_LLM_API_KEY", raising=False)
    a = _agent(tmp_path)
    out = _apply(a, {"llm": {"provider": "openai"}}, tmp_path)  # no key -> mock live, key_set False
    assert isinstance(a.llm, MockLLM)
    openai_entry = next(p for p in out["llm"]["providers"] if p["id"] == "openai")
    assert openai_entry["key_set"] is False


def test_apply_persists_key_and_hot_swaps(tmp_path):
    a = _agent(tmp_path)
    out = _apply(a, {"llm": {"provider": "openai", "api_key": "sk-live"}}, tmp_path)
    assert os.environ["OPENAI_API_KEY"] == "sk-live"
    assert (tmp_path / ".env").read_text()  # persisted
    import json

    assert "sk-live" not in json.dumps(out)
    entry = next(p for p in out["llm"]["providers"] if p["id"] == "openai")
    assert entry["key_set"] is True


# --- validation gate --------------------------------------------------------


def test_apply_auth_failure_raises_invalid_key(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "_validate_key", lambda *a, **k: (False, "401 unauthorized"))
    with pytest.raises(S.SettingsError) as e:
        _apply(_agent(tmp_path), {"llm": {"provider": "openai", "api_key": "bad"}}, tmp_path, do_validate=True)
    assert e.value.code == "invalid_key"


def test_apply_nonauth_validation_failure_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "_validate_key", lambda *a, **k: (False, "timeout"))
    out = _apply(_agent(tmp_path), {"llm": {"provider": "openai", "api_key": "k"}}, tmp_path, do_validate=True)
    assert out["llm"]["current"]["provider"] == "openai"  # not blocked


def test_validate_key_swallows_exceptions(monkeypatch):
    def boom(info, **k):
        raise RuntimeError("crash")

    monkeypatch.setattr("jarvis_backend.setup_wizard.validate_provider", boom)
    ok, msg = S._validate_key(None, "m", None, "k")
    assert ok is False and "RuntimeError" in msg


def test_looks_like_auth_failure():
    assert S._looks_like_auth_failure("HTTP 401 Unauthorized")
    assert S._looks_like_auth_failure("invalid api key")
    assert not S._looks_like_auth_failure("connection timeout")
    assert not S._looks_like_auth_failure("")
