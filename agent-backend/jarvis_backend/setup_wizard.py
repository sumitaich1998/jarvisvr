"""Install-time setup wizard: ``jarvis-backend setup`` (alias ``init``).

Asks the user which LLM provider to use and for their **API key** (masked,
non-echoing input via :mod:`getpass`), then writes/updates ``.env`` with the
provider, model, base_url, and key — preserving unrelated keys and ``chmod 600``.

Security:
* The key is read with ``getpass`` (never echoed) and **never printed or logged**
  (only a masked ``•••• (N chars)`` confirmation is shown).
* ``.env`` is written atomically and ``chmod 600`` (owner read/write only).

It is idempotent + re-runnable (reconfigure / add providers / switch default),
and supports a fully non-interactive mode for CI/automation.
"""

from __future__ import annotations

import getpass as _getpass
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import providers as P

_KEY_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*)=")
_ADDED_HEADER = "# --- Added/updated by `jarvis-backend setup` ---"


# ---------------------------------------------------------------------------
# Secret-safe helpers
# ---------------------------------------------------------------------------


def mask_secret(value: Optional[str]) -> str:
    """A confirmation string that reveals nothing about the key's content."""
    if not value:
        return "(none)"
    return "•" * min(len(value), 8) + f" ({len(value)} chars)"


def _format_value(value: str) -> str:
    if value == "" or re.search(r"[\s#\"']", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def model_env_var(provider_id: str) -> str:
    if provider_id == "openai":
        return "JARVIS_OPENAI_MODEL"
    if provider_id == "anthropic":
        return "JARVIS_ANTHROPIC_MODEL"
    return f"JARVIS_{provider_id.upper()}_MODEL"


def key_env_var(info: P.ProviderInfo) -> str:
    """Where the key is stored: the provider's conventional var, else generic."""
    return info.env_var or "JARVIS_LLM_API_KEY"


# ---------------------------------------------------------------------------
# .env writer (atomic + 0600, preserves unrelated keys, never logs values)
# ---------------------------------------------------------------------------


def update_env_file(path: os.PathLike | str, updates: dict[str, str]) -> None:
    """Set ``KEY=value`` for each item in ``updates``, preserving everything else."""
    path = Path(path)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    out: list[str] = []
    for line in existing:
        m = _KEY_RE.match(line)
        if m and m.group(2) in remaining:
            key = m.group(2)
            out.append(f"{key}={_format_value(remaining.pop(key))}")
        else:
            out.append(line)
    if remaining:
        if out and out[-1].strip() != "":
            out.append("")
        out.append(_ADDED_HEADER)
        for key, val in remaining.items():
            out.append(f"{key}={_format_value(val)}")
    text = "\n".join(out).rstrip("\n") + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)  # owner read/write only — protects the key at rest
    except OSError:
        pass


def build_settings(
    info: P.ProviderInfo,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> tuple[dict[str, str], set[str]]:
    """Return (``.env`` updates, set of secret keys) for a provider choice."""
    updates: dict[str, str] = {"JARVIS_LLM": info.id}
    if info.kind == P.KIND_MOCK:
        return updates, set()

    updates[model_env_var(info.id)] = model or info.default_model
    if base_url:
        updates[f"JARVIS_{info.id.upper()}_BASE_URL"] = base_url
    secrets: set[str] = set()
    if api_key:
        kv = key_env_var(info)
        updates[kv] = api_key
        secrets.add(kv)
    # litellm_only providers (Bedrock/Azure/Vertex/Cohere) need the universal adapter.
    updates["JARVIS_USE_LITELLM"] = "1" if info.kind == P.KIND_LITELLM_ONLY else "0"
    return updates, secrets


# ---------------------------------------------------------------------------
# Optional best-effort key validation (never raises, never blocks setup)
# ---------------------------------------------------------------------------


def validate_provider(
    info: P.ProviderInfo,
    *,
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    timeout: float = 15.0,
) -> tuple[bool, str]:
    """Try a tiny live completion. Returns (ok, message); never raises."""
    import asyncio

    try:
        from .agent.llm import LLMMessage, MockLLM, create_llm
        from .config import Config
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - imports always resolve
        return False, f"could not import provider layer ({exc})"

    cfg = Config(
        llm_provider=info.id,
        llm_model=model,
        llm_base_url=base_url,
        llm_api_key=api_key,  # generic fallback so resolve() finds the key
    )
    try:
        llm = create_llm(cfg)
    except Exception as exc:  # noqa: BLE001
        return False, f"could not build provider ({exc})"
    if isinstance(llm, MockLLM):
        return False, "fell back to mock (missing key/SDK — install '.[providers]'?)"

    async def _ping() -> str:
        res = await llm.complete([LLMMessage(role="user", content="ping")], [])
        return res.content or ""

    try:
        asyncio.run(asyncio.wait_for(_ping(), timeout=timeout))
        return True, "OK"
    except Exception as exc:  # noqa: BLE001 - network/auth/etc.
        return False, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------


@dataclass
class SetupResult:
    provider_id: str
    env_path: Path
    validated: Optional[bool]  # None = not attempted
    updates_keys: list[str]


def _print_provider_table(print_fn: Callable[[str], None]) -> list[P.ProviderInfo]:
    provs = P.all_providers()
    print_fn("")
    print_fn("Supported LLM providers:")
    for i, p in enumerate(provs, 1):
        key = p.env_var or ("(no key)" if p.kind == P.KIND_MOCK or not p.requires_key else "")
        bits = [f"  {i:>2}. {p.display_name} [{p.id}]"]
        if key:
            bits.append(f"key={key}")
        if p.default_model:
            bits.append(f"model={p.default_model}")
        if p.needs_base_url:
            bits.append("needs base_url")
        print_fn("   ".join(bits))
    print_fn("")
    return provs


def _select_provider(
    raw: str, provs: list[P.ProviderInfo]
) -> Optional[P.ProviderInfo]:
    raw = (raw or "").strip()
    if not raw:
        return P.get_provider("mock")
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(provs):
            return provs[idx]
        return None
    return P.get_provider(raw)


def run_setup(
    *,
    env_path: os.PathLike | str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    non_interactive: bool = False,
    assume_yes: bool = False,
    do_validate: Optional[bool] = None,  # None = ask (interactive); else force
    input_fn: Callable[[str], str] = input,
    getpass_fn: Callable[[str], str] = _getpass.getpass,
    print_fn: Callable[[str], None] = print,
    env: Optional[dict[str, str]] = None,
) -> SetupResult:
    """Run the setup wizard (interactive unless ``non_interactive``)."""
    env = env if env is not None else dict(os.environ)
    env_path = Path(env_path)

    if non_interactive:
        return _run_non_interactive(
            env_path=env_path, provider=provider, model=model, base_url=base_url,
            api_key=api_key, do_validate=bool(do_validate), print_fn=print_fn, env=env,
        )

    print_fn("")
    print_fn("=== JarvisVR setup — connect your LLM ===")
    provs = _print_provider_table(print_fn)
    raw = input_fn("Select a provider [number or id] (Enter = mock/offline): ")
    info = _select_provider(raw, provs)
    if info is None:
        print_fn(f"Unknown provider {raw!r}; defaulting to mock (offline).")
        info = P.get_provider("mock")

    if info.kind == P.KIND_MOCK:
        updates, _ = build_settings(info)
        update_env_file(env_path, updates)
        print_fn(f"\nConfigured: mock (offline, no API key). Wrote {env_path}.")
        return SetupResult("mock", env_path, None, list(updates))

    print_fn(f"\nConfiguring {info.display_name} [{info.id}].")
    if info.notes:
        print_fn(f"  note: {info.notes}")

    chosen_model = (input_fn(f"Model [{info.default_model}]: ").strip() or info.default_model)

    chosen_base_url = base_url
    if info.needs_base_url:
        default_bu = info.default_base_url or ""
        prompt = f"Base URL [{default_bu}]: " if default_bu else "Base URL: "
        chosen_base_url = input_fn(prompt).strip() or info.default_base_url

    # Masked, non-echoing key entry.
    if info.requires_key:
        prompt = f"{info.env_var} (input hidden): "
    else:
        prompt = "API key (optional — press Enter to skip for local servers): "
    chosen_key = getpass_fn(prompt).strip() or None
    if info.requires_key and not chosen_key:
        print_fn(
            "  ! No key entered. Saving config without a key — JarvisVR will run "
            "in mock mode until you set it (re-run `jarvis-backend setup`)."
        )

    validated: Optional[bool] = None
    want_validate = do_validate
    if want_validate is None and not assume_yes and chosen_key:
        ans = input_fn("Validate the key now with a tiny test call? [y/N]: ").strip().lower()
        want_validate = ans.startswith("y")
    if want_validate and chosen_key:
        print_fn("  validating… (this makes one small API call)")
        ok, msg = validate_provider(
            info, model=chosen_model, base_url=chosen_base_url, api_key=chosen_key
        )
        validated = ok
        print_fn(f"  validation: {'OK' if ok else 'could not validate — ' + msg}")
        if not ok:
            print_fn("  (continuing anyway — validation is optional)")

    updates, secrets = build_settings(
        info, model=chosen_model, base_url=chosen_base_url, api_key=chosen_key
    )
    update_env_file(env_path, updates)

    print_fn("")
    print_fn(f"Saved to {env_path} (chmod 600):")
    print_fn(f"  JARVIS_LLM = {info.id}")
    print_fn(f"  {model_env_var(info.id)} = {chosen_model}")
    if chosen_base_url:
        print_fn(f"  JARVIS_{info.id.upper()}_BASE_URL = {chosen_base_url}")
    if chosen_key:
        print_fn(f"  {key_env_var(info)} = {mask_secret(chosen_key)}  (stored, never shown)")
    print_fn("\nDone. Start the brain with:  python -m jarvis_backend")
    return SetupResult(info.id, env_path, validated, list(updates))


def _run_non_interactive(
    *,
    env_path: Path,
    provider: Optional[str],
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    do_validate: bool,
    print_fn: Callable[[str], None],
    env: dict[str, str],
) -> SetupResult:
    info = P.get_provider(provider) or P.get_provider("mock")
    if info.kind == P.KIND_MOCK:
        updates, _ = build_settings(info)
        update_env_file(env_path, updates)
        print_fn(f"[setup] configured mock (offline); wrote {env_path}")
        return SetupResult("mock", env_path, None, list(updates))

    chosen_model = model or info.default_model
    chosen_base_url = base_url or info.default_base_url
    chosen_key = (
        api_key
        or (env.get(info.env_var) if info.env_var else None)
        or env.get("JARVIS_LLM_API_KEY")
    )
    if info.requires_key and not chosen_key:
        print_fn(
            f"[setup] WARNING: no API key for {info.id} "
            f"(set {info.env_var} or pass --api-key); writing config without it."
        )

    validated: Optional[bool] = None
    if do_validate and chosen_key:
        ok, msg = validate_provider(
            info, model=chosen_model, base_url=chosen_base_url, api_key=chosen_key
        )
        validated = ok
        print_fn(f"[setup] validation: {'OK' if ok else 'failed — ' + msg}")

    updates, _ = build_settings(
        info, model=chosen_model, base_url=chosen_base_url, api_key=chosen_key
    )
    update_env_file(env_path, updates)
    print_fn(f"[setup] configured {info.id} (model={chosen_model}); wrote {env_path} (chmod 600)")
    return SetupResult(info.id, env_path, validated, list(updates))


__all__ = [
    "run_setup",
    "update_env_file",
    "build_settings",
    "validate_provider",
    "mask_secret",
    "model_env_var",
    "key_env_var",
    "SetupResult",
]
