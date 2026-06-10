"""Setup-wizard tests: writes a correct .env, masks the key, idempotent, 0600."""

from __future__ import annotations

import stat
from pathlib import Path

from jarvis_backend import providers as P
from jarvis_backend import setup_wizard as W


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


# --- .env writer ------------------------------------------------------------


def test_update_env_file_creates_with_0600(tmp_path):
    env = tmp_path / ".env"
    W.update_env_file(env, {"JARVIS_LLM": "openai", "OPENAI_API_KEY": "sk-xyz"})
    text = env.read_text()
    assert "JARVIS_LLM=openai" in text
    assert "OPENAI_API_KEY=sk-xyz" in text
    assert _mode(env) == 0o600


def test_update_env_preserves_unrelated_and_updates_in_place(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nFOO=bar\nOPENAI_API_KEY=old\nJARVIS_PORT=8765\n")
    W.update_env_file(env, {"OPENAI_API_KEY": "new", "JARVIS_LLM": "openai"})
    lines = env.read_text().splitlines()
    assert "FOO=bar" in lines
    assert "JARVIS_PORT=8765" in lines
    assert "OPENAI_API_KEY=new" in lines  # updated in place
    assert "OPENAI_API_KEY=old" not in lines
    assert "JARVIS_LLM=openai" in lines  # appended
    # exactly one OPENAI_API_KEY line
    assert sum(1 for ln in lines if ln.startswith("OPENAI_API_KEY=")) == 1


def test_update_env_quotes_values_with_spaces(tmp_path):
    env = tmp_path / ".env"
    W.update_env_file(env, {"JARVIS_NOTE": "hello world"})
    assert 'JARVIS_NOTE="hello world"' in env.read_text()


# --- build_settings ---------------------------------------------------------


def test_build_settings_openai():
    info = P.get_provider("openai")
    updates, secrets = W.build_settings(info, model="gpt-4o", api_key="sk-1")
    assert updates["JARVIS_LLM"] == "openai"
    assert updates["JARVIS_OPENAI_MODEL"] == "gpt-4o"
    assert updates["OPENAI_API_KEY"] == "sk-1"
    assert updates["JARVIS_USE_LITELLM"] == "0"
    assert secrets == {"OPENAI_API_KEY"}


def test_build_settings_mock():
    updates, secrets = W.build_settings(P.get_provider("mock"))
    assert updates == {"JARVIS_LLM": "mock"}
    assert secrets == set()


def test_build_settings_custom_and_litellm_only():
    custom = W.build_settings(
        P.get_provider("custom"), model="m", base_url="http://h/v1", api_key="k"
    )[0]
    assert custom["JARVIS_CUSTOM_BASE_URL"] == "http://h/v1"
    assert custom["JARVIS_LLM_API_KEY"] == "k"  # no conventional env var -> generic
    assert custom["JARVIS_USE_LITELLM"] == "0"

    bedrock = W.build_settings(P.get_provider("bedrock"))[0]
    assert bedrock["JARVIS_USE_LITELLM"] == "1"  # litellm_only


def test_mask_secret_reveals_nothing():
    m = W.mask_secret("super-secret-key-123")
    assert "super" not in m and "123" not in m
    assert "20 chars" in m


# --- interactive flow (injected IO) -----------------------------------------


def test_interactive_openai_masks_key_and_writes(tmp_path):
    env = tmp_path / ".env"
    inputs = iter(["openai", "", "n"])  # provider, model(default), validate? no
    printed: list[str] = []

    def fake_input(prompt: str = "") -> str:
        return next(inputs)

    def fake_getpass(prompt: str = "") -> str:
        return "sk-secret-123"

    result = W.run_setup(
        env_path=env,
        input_fn=fake_input,
        getpass_fn=fake_getpass,
        print_fn=printed.append,
        env={},
    )
    assert result.provider_id == "openai"
    text = env.read_text()
    assert "OPENAI_API_KEY=sk-secret-123" in text  # stored in file
    assert "JARVIS_LLM=openai" in text
    assert _mode(env) == 0o600
    # the secret must never appear in any printed line
    joined = "\n".join(printed)
    assert "sk-secret-123" not in joined


def test_interactive_mock_skips_getpass(tmp_path):
    env = tmp_path / ".env"
    inputs = iter(["mock"])
    called = {"getpass": False}

    def fake_getpass(prompt: str = "") -> str:
        called["getpass"] = True
        return "should-not-be-called"

    result = W.run_setup(
        env_path=env,
        input_fn=lambda p="": next(inputs),
        getpass_fn=fake_getpass,
        print_fn=lambda s: None,
        env={},
    )
    assert result.provider_id == "mock"
    assert called["getpass"] is False
    assert "JARVIS_LLM=mock" in env.read_text()


# --- non-interactive flow ---------------------------------------------------


def test_non_interactive_writes_provider(tmp_path):
    env = tmp_path / ".env"
    result = W.run_setup(
        env_path=env,
        provider="groq",
        api_key="gk-1",
        non_interactive=True,
        print_fn=lambda s: None,
        env={},
    )
    assert result.provider_id == "groq"
    text = env.read_text()
    assert "JARVIS_LLM=groq" in text
    assert "GROQ_API_KEY=gk-1" in text
    assert f"JARVIS_GROQ_MODEL={P.get_provider('groq').default_model}" in text
    assert _mode(env) == 0o600


def test_non_interactive_idempotent_reconfigure(tmp_path):
    env = tmp_path / ".env"
    env.write_text("FOO=bar\n")
    W.run_setup(env_path=env, provider="openai", model="gpt-4o", api_key="sk-1",
                non_interactive=True, print_fn=lambda s: None, env={})
    W.run_setup(env_path=env, provider="openai", model="gpt-4o-mini", api_key="sk-2",
                non_interactive=True, print_fn=lambda s: None, env={})
    lines = env.read_text().splitlines()
    assert "FOO=bar" in lines  # unrelated preserved
    assert sum(1 for ln in lines if ln.startswith("JARVIS_LLM=")) == 1
    assert "JARVIS_OPENAI_MODEL=gpt-4o-mini" in lines  # updated
    assert "OPENAI_API_KEY=sk-2" in lines


def test_non_interactive_no_key_does_not_fail(tmp_path):
    env = tmp_path / ".env"
    # No key provided and none in env -> should still write config, not raise.
    result = W.run_setup(
        env_path=env, provider="openai", non_interactive=True,
        print_fn=lambda s: None, env={},
    )
    assert result.provider_id == "openai"
    assert "JARVIS_LLM=openai" in env.read_text()
