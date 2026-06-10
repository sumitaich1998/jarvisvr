"""CLI entrypoint: ``python -m jarvis_backend`` / ``jarvis-backend``.

Subcommands:
* (default) / ``serve`` — run the WebSocket server.
* ``setup`` / ``init`` — interactive wizard to pick an LLM provider + enter the
  API key (masked); writes ``.env`` (chmod 600). Supports ``--non-interactive``.
* ``providers`` — list every supported LLM provider.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import Config
from .logging_setup import configure_logging
from .server import run_server

_AGENT_BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = _AGENT_BACKEND_DIR / ".env"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jarvis-backend",
        description="JarvisVR agent-backend — the multi-provider LLM 'brain'.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="Run the WebSocket server (this is the default).")
    sub.add_parser("providers", help="List the supported LLM providers and exit.")

    for name in ("setup", "init"):
        sp = sub.add_parser(
            name,
            help="Configure your LLM provider + API key (writes .env, chmod 600).",
        )
        sp.add_argument("--provider", help="Provider id (e.g. openai, anthropic, gemini, groq, ollama).")
        sp.add_argument("--model", help="Model name (defaults to the provider's default).")
        sp.add_argument("--base-url", dest="base_url", help="Custom/local OpenAI-compatible base URL.")
        sp.add_argument("--api-key", dest="api_key", help="API key (avoid on shared shells; prefer interactive or env).")
        sp.add_argument("--env-file", dest="env_file", default=str(DEFAULT_ENV_FILE), help="Path to the .env to write.")
        sp.add_argument("--non-interactive", "--ci", dest="non_interactive", action="store_true", help="No prompts (for CI/automation).")
        sp.add_argument("--yes", "-y", dest="assume_yes", action="store_true", help="Don't ask to validate; accept defaults.")
        sp.add_argument("--validate", dest="validate", action="store_true", help="Validate the key with a live call.")
        sp.add_argument("--no-validate", dest="no_validate", action="store_true", help="Never attempt validation.")
    return parser


def _cmd_serve() -> int:
    config = Config.from_env()
    configure_logging(config.log_level, json_logs=config.log_json)
    log = logging.getLogger("jarvis")
    log.info("starting JarvisVR agent-backend v%s", _version())
    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        log.info("shutting down (keyboard interrupt)")
    return 0


def _cmd_providers() -> int:
    from . import providers as P

    print("JarvisVR — supported LLM providers (set JARVIS_LLM=<id>):\n")
    for p in P.all_providers():
        caps = ",".join(
            c for c, on in (("tools", p.supports_tools), ("vision", p.supports_vision)) if on
        ) or "-"
        base = "required" if p.needs_base_url else (p.default_base_url or "-")
        print(f"  {p.id:<12} {p.display_name}")
        print(
            f"     key_env={p.env_var or '(none)'}   default_model={p.default_model or '-'}"
            f"   base_url={base}   caps={caps}"
        )
    print("\nRun `jarvis-backend setup` to configure one (it will ask for your API key).")
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    from .setup_wizard import run_setup

    do_validate = None
    if getattr(args, "validate", False):
        do_validate = True
    if getattr(args, "no_validate", False):
        do_validate = False
    try:
        run_setup(
            env_path=args.env_file,
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            non_interactive=args.non_interactive,
            assume_yes=args.assume_yes,
            do_validate=do_validate,
        )
        return 0
    except KeyboardInterrupt:
        print("\nsetup cancelled.")
        return 130


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"
    if command in ("setup", "init"):
        return _cmd_setup(args)
    if command == "providers":
        return _cmd_providers()
    return _cmd_serve()


def _version() -> str:
    try:
        from . import __version__

        return __version__
    except Exception:  # noqa: BLE001
        return "0.0.0"


if __name__ == "__main__":  # pragma: no cover - module-as-script entrypoint
    sys.exit(main())
