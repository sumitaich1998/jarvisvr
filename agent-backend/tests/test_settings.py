"""Runtime settings (§5.15): catalog, hot-swap, secure persist, no key leakage."""

from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

import pytest
import websockets

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import GenericOpenAILLM, MockLLM
from jarvis_backend.config import Config
from jarvis_backend.server import start_server
from jarvis_backend.settings_service import (
    SettingsError,
    apply_settings_update,
    build_server_settings,
)

_TOUCHED_ENV = [
    "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "JARVIS_LLM_API_KEY",
]


@pytest.fixture(autouse=True)
def _clean_env():
    """Clean baseline + restore (settings code mutates os.environ directly)."""
    saved = {k: os.environ.get(k) for k in _TOUCHED_ENV}
    for k in _TOUCHED_ENV:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _agent(tmp_path: Path) -> Agent:
    cfg = Config(
        llm_provider="mock", holo_registry_path=None, data_dir=Path(tmp_path),
        env_file=Path(tmp_path) / ".env",
    )
    return Agent.build(cfg, MockLLM())


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


# --- build_server_settings (reads) ------------------------------------------


def test_server_settings_catalog_and_no_key(tmp_path):
    agent = _agent(tmp_path)
    payload = build_server_settings(agent.config)
    assert payload["llm"]["current"]["provider"] == "mock"
    assert payload["llm"]["current"]["key_set"] is False
    ids = {p["id"] for p in payload["llm"]["providers"]}
    assert {"mock", "openai", "anthropic", "gemini", "groq", "ollama"} <= ids
    # shape of an entry
    openai = next(p for p in payload["llm"]["providers"] if p["id"] == "openai")
    assert openai["needs_key"] is True
    assert "tools" in openai["capabilities"] and "vision" in openai["capabilities"]
    # SECURITY: never any key material anywhere in the payload
    assert "api_key" not in json.dumps(payload)


def test_key_set_reflects_env(tmp_path):
    agent = _agent(tmp_path)
    assert all(
        not p["key_set"] for p in build_server_settings(agent.config)["llm"]["providers"]
    )
    os.environ["OPENAI_API_KEY"] = "sk-present"
    payload = build_server_settings(agent.config)
    openai = next(p for p in payload["llm"]["providers"] if p["id"] == "openai")
    assert openai["key_set"] is True
    assert "sk-present" not in json.dumps(payload)  # only key_set, never the value


# --- apply_settings_update (writes: validate -> persist -> hot-swap) ---------


def test_update_persists_and_hot_swaps(tmp_path):
    agent = _agent(tmp_path)
    assert isinstance(agent.llm, MockLLM)
    env_path = Path(tmp_path) / ".env"

    settings = apply_settings_update(
        agent,
        {"llm": {"provider": "groq", "model": "llama-3.3-70b-versatile", "api_key": "gk-SECRET"}},
        env_path=env_path,
    )

    # hot-swapped live LLM
    assert isinstance(agent.llm, GenericOpenAILLM)
    assert agent.llm.name == "groq"
    assert agent.llm.model == "llama-3.3-70b-versatile"

    # returned settings reflect the change, with key_set True and NO key
    assert settings["llm"]["current"]["provider"] == "groq"
    assert settings["llm"]["current"]["model"] == "llama-3.3-70b-versatile"
    assert settings["llm"]["current"]["key_set"] is True
    assert "gk-SECRET" not in json.dumps(settings)
    assert "api_key" not in json.dumps(settings)

    # persisted to .env (chmod 600), key present only in the file
    text = env_path.read_text()
    assert "JARVIS_LLM=groq" in text
    assert "GROQ_API_KEY=gk-SECRET" in text
    assert _mode(env_path) == 0o600


def test_update_without_key_preserves_existing(tmp_path):
    agent = _agent(tmp_path)
    env_path = Path(tmp_path) / ".env"
    apply_settings_update(agent, {"llm": {"provider": "openai", "api_key": "sk-1"}}, env_path=env_path)
    # change only the model; key must be preserved in .env
    apply_settings_update(agent, {"llm": {"provider": "openai", "model": "gpt-4o"}}, env_path=env_path)
    text = env_path.read_text()
    assert "OPENAI_API_KEY=sk-1" in text
    assert "JARVIS_OPENAI_MODEL=gpt-4o" in text


def test_update_unknown_provider_raises(tmp_path):
    agent = _agent(tmp_path)
    with pytest.raises(SettingsError) as ei:
        apply_settings_update(agent, {"llm": {"provider": "nope"}}, env_path=Path(tmp_path) / ".env")
    assert ei.value.code == "provider_unavailable"


def test_update_malformed_raises_invalid_settings(tmp_path):
    agent = _agent(tmp_path)
    env_path = Path(tmp_path) / ".env"
    with pytest.raises(SettingsError) as ei:
        apply_settings_update(agent, {"llm": "not-an-object"}, env_path=env_path)
    assert ei.value.code == "invalid_settings"
    with pytest.raises(SettingsError) as ei2:
        apply_settings_update(agent, {"llm": {"provider": 123}}, env_path=env_path)
    assert ei2.value.code == "invalid_settings"


def test_switch_to_mock_offline(tmp_path):
    agent = _agent(tmp_path)
    apply_settings_update(agent, {"llm": {"provider": "groq", "api_key": "gk"}}, env_path=Path(tmp_path) / ".env")
    assert isinstance(agent.llm, GenericOpenAILLM)
    settings = apply_settings_update(agent, {"llm": {"provider": "mock"}}, env_path=Path(tmp_path) / ".env")
    assert isinstance(agent.llm, MockLLM)
    assert settings["llm"]["current"]["provider"] == "mock"


# --- socket integration (the real protocol path) ----------------------------


async def _recv(ws) -> protocol.Envelope:
    return protocol.parse_inbound(await ws.recv())


async def _wait_for(ws, type_, timeout=5.0) -> protocol.Envelope:
    async def loop():
        while True:
            env = await _recv(ws)
            if env.type == type_:
                return env

    return await asyncio.wait_for(loop(), timeout)


async def test_settings_over_socket_no_key_leak(tmp_path):
    cfg = Config(
        host="127.0.0.1", port=0, llm_provider="mock", holo_registry_path=None,
        data_dir=Path(tmp_path), env_file=Path(tmp_path) / ".env",
    )
    server, _agent = await start_server(cfg)
    port = server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}/jarvis"
    received_raw: list[str] = []
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(protocol.make("client.hello", {"device": "quest3"}).to_json())
            ack = await _wait_for(ws, "server.hello_ack")
            assert ack.payload.get("settings") is True  # advertises §5.15 support
            session = ack.payload["session"]

            async def send(type_, payload):
                await ws.send(protocol.make(type_, payload, session=session).to_json())

            # settings_get -> server.settings catalog
            await send("client.settings_get", {"section": "llm"})
            got = await _wait_for(ws, "server.settings")
            received_raw.append(got.to_json())
            assert got.payload["llm"]["current"]["provider"] == "mock"
            assert any(p["id"] == "groq" for p in got.payload["llm"]["providers"])

            # settings_update with a secret key -> server.settings reflects groq
            await send("client.settings_update", {
                "llm": {"provider": "groq", "model": "llama-3.3-70b-versatile", "api_key": "gk-WIRE-SECRET"}
            })
            updated = await _wait_for(ws, "server.settings")
            received_raw.append(updated.to_json())
            cur = updated.payload["llm"]["current"]
            assert cur["provider"] == "groq"
            assert cur["model"] == "llama-3.3-70b-versatile"
            assert cur["key_set"] is True

            # unknown provider -> server.error provider_unavailable
            await send("client.settings_update", {"llm": {"provider": "definitely-not-real"}})
            err = await _wait_for(ws, "server.error")
            received_raw.append(err.to_json())
            assert err.payload["code"] == "provider_unavailable"

        # The secret key must NEVER appear in any frame the server sent back.
        blob = "\n".join(received_raw)
        assert "gk-WIRE-SECRET" not in blob
        assert "api_key" not in blob
        # but it IS persisted to the 0600 .env
        env_text = (Path(tmp_path) / ".env").read_text()
        assert "GROQ_API_KEY=gk-WIRE-SECRET" in env_text
    finally:
        server.close()
        await server.wait_closed()
