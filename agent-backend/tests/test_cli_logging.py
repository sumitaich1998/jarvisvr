"""CLI entrypoint (`__main__`) + structured logging setup."""

from __future__ import annotations

import logging

import pytest

import jarvis_backend
from jarvis_backend import __main__ as cli
from jarvis_backend import logging_setup


@pytest.fixture
def restore_root_logging():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)


# --- logging_setup ----------------------------------------------------------


def test_configure_logging_plain_is_idempotent(restore_root_logging):
    logging_setup.configure_logging("DEBUG")
    n1 = len(logging.getLogger().handlers)
    logging_setup.configure_logging("DEBUG")  # reconfigure -> still one handler
    assert len(logging.getLogger().handlers) == n1 == 1
    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("websockets").level == logging.WARNING


def test_configure_logging_json_formatter(restore_root_logging):
    logging_setup.configure_logging(logging.INFO, json_logs=True)
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler.formatter, logging_setup._JsonFormatter)


def test_json_formatter_serializes_record_with_exc_and_extra():
    fmt = logging_setup._JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        rec = logging.LogRecord(
            "jarvis", logging.ERROR, __file__, 1, "msg %s", ("x",), exc_info=__import__("sys").exc_info()
        )
    rec.custom_field = "extra-value"  # structured extra
    out = fmt.format(rec)
    import json

    data = json.loads(out)
    assert data["level"] == "ERROR"
    assert data["logger"] == "jarvis"
    assert data["msg"] == "msg x"
    assert "exc" in data
    assert data["custom_field"] == "extra-value"


def test_get_logger_returns_named_logger():
    assert logging_setup.get_logger("jarvis.test").name == "jarvis.test"


# --- __main__ ---------------------------------------------------------------


def test_main_providers_command(capsys):
    assert cli.main(["providers"]) == 0
    out = capsys.readouterr().out
    assert "openai" in out and "anthropic" in out and "mock" in out


def test_main_setup_non_interactive(tmp_path, capsys):
    env = tmp_path / ".env"
    rc = cli.main(["setup", "--non-interactive", "--provider", "mock", "--env-file", str(env)])
    assert rc == 0
    assert "JARVIS_LLM=mock" in env.read_text()


def test_main_setup_with_validate_flags(tmp_path, monkeypatch):
    captured = {}

    def fake_run_setup(**kwargs):
        captured.update(kwargs)
        from jarvis_backend.setup_wizard import SetupResult

        return SetupResult("openai", tmp_path / ".env", None, [])

    monkeypatch.setattr("jarvis_backend.setup_wizard.run_setup", fake_run_setup)
    rc = cli.main(["init", "--provider", "openai", "--no-validate", "--env-file", str(tmp_path / ".env")])
    assert rc == 0
    assert captured["do_validate"] is False
    assert captured["provider"] == "openai"


def test_main_setup_validate_true(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "jarvis_backend.setup_wizard.run_setup",
        lambda **k: captured.update(k) or __import__("jarvis_backend.setup_wizard", fromlist=["SetupResult"]).SetupResult("openai", tmp_path, True, []),
    )
    cli.main(["setup", "--validate", "--env-file", str(tmp_path / ".env")])
    assert captured["do_validate"] is True


def test_main_setup_keyboardinterrupt_returns_130(tmp_path, monkeypatch, capsys):
    def boom(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("jarvis_backend.setup_wizard.run_setup", boom)
    rc = cli.main(["setup", "--env-file", str(tmp_path / ".env")])
    assert rc == 130
    assert "cancelled" in capsys.readouterr().out


def test_main_serve_default(monkeypatch):
    async def fake_run_server(config):
        return None

    monkeypatch.setattr(cli, "run_server", fake_run_server)
    monkeypatch.setattr(cli, "configure_logging", lambda *a, **k: None)
    assert cli.main([]) == 0  # default command is "serve"
    assert cli.main(["serve"]) == 0


def test_main_serve_keyboard_interrupt(monkeypatch):
    async def boom(config):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_server", boom)
    monkeypatch.setattr(cli, "configure_logging", lambda *a, **k: None)
    assert cli.main(["serve"]) == 0  # handled gracefully


def test_version_helper_and_fallback(monkeypatch):
    assert cli._version() == jarvis_backend.__version__
    monkeypatch.delattr(jarvis_backend, "__version__", raising=False)
    assert cli._version() == "0.0.0"
