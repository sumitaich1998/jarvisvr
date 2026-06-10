"""Runtime settings service (PROTOCOL.md §5.15).

Builds the ``server.settings`` payload (provider catalog + current config, with
``key_set`` booleans only — *never* a key) and applies ``client.settings_update``
by:

1. validating the requested provider/model/base_url,
2. persisting any new ``api_key`` securely by **reusing the setup wizard's atomic,
   ``chmod 600`` ``.env`` writer** (the key is never logged/echoed),
3. updating the live :class:`~jarvis_backend.config.Config` + process env, and
4. **hot-swapping** the active LLM via :func:`create_llm` so the next turn uses it.

Errors raise :class:`SettingsError` with a PROTOCOL.md §5.15 code:
``invalid_settings`` | ``provider_unavailable`` | ``invalid_key``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from . import providers as P
from .agent.llm import MockLLM, create_llm

log = logging.getLogger("jarvis.settings")


class SettingsError(Exception):
    """A settings_update failure mapped to a server.error code (§5.15)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Reads — server.settings (no keys, ever)
# ---------------------------------------------------------------------------


def _provider_entry(info: P.ProviderInfo, config) -> dict[str, Any]:
    return {
        "id": info.id,
        "name": info.display_name,
        "default_model": info.default_model,
        "models": list(info.default_models),
        "needs_key": info.requires_key,
        "needs_base_url": info.needs_base_url,
        "key_set": P.key_is_set(info, config),
        "capabilities": {"tools": info.supports_tools, "vision": info.supports_vision},
    }


def build_server_settings(config) -> dict[str, Any]:
    """The ``server.settings`` payload: current config + provider catalog.

    Contains only a ``key_set`` boolean per provider — the API key itself is
    never included.
    """
    resolved = P.resolve(config)
    active = P.get_provider(resolved.provider_id)
    current = {
        "provider": resolved.provider_id,
        "model": resolved.model,
        "base_url": resolved.base_url,  # may be None (allowed by schema)
        "key_set": P.key_is_set(active, config) if active else False,
    }
    return {
        "llm": {
            "current": current,
            "providers": [_provider_entry(info, config) for info in P.all_providers()],
        }
    }


# ---------------------------------------------------------------------------
# Writes — client.settings_update (validate -> persist -> hot-swap)
# ---------------------------------------------------------------------------


def _as_optional_str(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SettingsError(
            P_ERR_INVALID, f"'{field}' must be a string (got {type(value).__name__})"
        )
    return value


P_ERR_INVALID = "invalid_settings"
P_ERR_PROVIDER = "provider_unavailable"
P_ERR_KEY = "invalid_key"


def apply_settings_update(
    agent,
    payload: dict[str, Any],
    *,
    env_path,
    do_validate: bool = False,
) -> dict[str, Any]:
    """Apply a ``client.settings_update`` payload; returns a fresh server.settings.

    Idempotent and safe to call between turns. Never logs the API key.
    """
    if not isinstance(payload, dict):
        raise SettingsError(P_ERR_INVALID, "settings_update payload must be an object")
    llm = payload.get("llm")
    if not isinstance(llm, dict):
        raise SettingsError(P_ERR_INVALID, "settings_update requires an 'llm' object")

    config = agent.config
    current = P.resolve(config)

    provider_id = _as_optional_str(llm.get("provider"), "provider")
    provider_id = (provider_id or current.provider_id).strip().lower()
    info = P.get_provider(provider_id)
    if info is None:
        raise SettingsError(
            P_ERR_PROVIDER,
            f"unknown provider '{provider_id}' (see server.settings.llm.providers)",
        )

    model = _as_optional_str(llm.get("model"), "model")
    if not model:
        model = current.model if provider_id == current.provider_id else info.default_model

    # base_url: present (incl. explicit null) overrides; absent keeps current.
    if "base_url" in llm:
        base_url = _as_optional_str(llm.get("base_url"), "base_url")
    else:
        base_url = current.base_url if provider_id == current.provider_id else info.default_base_url

    api_key = _as_optional_str(llm.get("api_key"), "api_key")
    api_key = api_key or None  # empty string == "no change"

    # Optional best-effort live validation (off by default; never logs the key).
    if do_validate and api_key and info.kind != P.KIND_MOCK:
        ok, why = _validate_key(info, model, base_url, api_key)
        if not ok and _looks_like_auth_failure(why):
            raise SettingsError(P_ERR_KEY, f"key validation failed: {why}")

    # 1) Persist via the wizard's atomic, chmod-600 .env writer (key never logged).
    from .setup_wizard import build_settings, update_env_file

    updates, _secret_keys = build_settings(
        info, model=model, base_url=base_url, api_key=api_key
    )
    update_env_file(env_path, updates)

    # 2) Update the live config + process env so resolve()/create_llm pick it up now.
    config.llm_provider = info.id
    config.llm_model = model
    config.llm_base_url = base_url
    config.use_litellm = info.kind == P.KIND_LITELLM_ONLY
    if api_key:
        config.llm_api_key = api_key
        key_var = info.env_var or "JARVIS_LLM_API_KEY"
        os.environ[key_var] = api_key  # beats any stale env key for resolve()

    # 3) Hot-swap the live LLM (graceful mock fallback if a key/SDK is missing).
    new_llm = create_llm(config)
    agent.set_llm(new_llm)
    if isinstance(new_llm, MockLLM) and info.kind != P.KIND_MOCK:
        log.warning(
            "settings_update: provider %s selected but fell back to mock "
            "(missing key/SDK?). key_set reflects whether a key is stored.",
            info.id,
        )
    log.info(
        "settings_update: provider=%s model=%s base_url=%s key_provided=%s -> live=%s",
        info.id, model, base_url, bool(api_key), new_llm.name,
    )

    return build_server_settings(config)


def _validate_key(info, model, base_url, api_key) -> tuple[bool, str]:
    try:
        from .setup_wizard import validate_provider

        return validate_provider(info, model=model, base_url=base_url, api_key=api_key)
    except Exception as exc:  # noqa: BLE001 - validation must never crash settings
        return False, f"{type(exc).__name__}: {exc}"


def _looks_like_auth_failure(message: str) -> bool:
    low = (message or "").lower()
    return any(k in low for k in ("auth", "401", "403", "invalid api key", "unauthorized", "permission"))


__all__ = ["SettingsError", "build_server_settings", "apply_settings_update"]
