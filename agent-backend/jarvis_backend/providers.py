"""LLM provider registry + resolution.

A single source of truth describing every LLM provider JarvisVR can talk to: its
id, display name, the conventional API-key env var, default model(s), whether it
needs a ``base_url``, capabilities (tools/vision), and how to route it.

Providers reach a real model one of three ways (see ``kind``):

* ``native_openai`` / ``native_anthropic`` — first-party SDK paths.
* ``openai_compatible`` — any OpenAI-compatible ``/chat/completions`` endpoint
  (Groq, OpenRouter, DeepSeek, xAI, Together, Mistral, Gemini-OpenAI, Ollama,
  LM Studio, vLLM, custom…). Works over plain ``httpx`` — no extra SDK needed.
* ``litellm_only`` — routed through the optional **LiteLLM** universal adapter
  (Bedrock, Azure, Vertex, Cohere…). Requires the ``[providers]`` extra.

Any provider can *also* be forced through LiteLLM (``JARVIS_USE_LITELLM=1``).
``resolve()`` turns a :class:`~jarvis_backend.config.Config` + environment into a
concrete :class:`ResolvedLLM` (provider/model/base_url/api_key), applying the
key-resolution precedence: provider env var → generic ``JARVIS_LLM_API_KEY``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional

# Routing kinds.
KIND_MOCK = "mock"
KIND_NATIVE_OPENAI = "native_openai"
KIND_NATIVE_ANTHROPIC = "native_anthropic"
KIND_OPENAI_COMPATIBLE = "openai_compatible"
KIND_LITELLM_ONLY = "litellm_only"


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    display_name: str
    kind: str
    default_models: list[str]
    env_var: Optional[str] = None  # conventional API-key env var (None = no key)
    needs_base_url: bool = False
    default_base_url: Optional[str] = None
    litellm_prefix: str = ""  # prepended to the model for litellm routing
    supports_tools: bool = True
    supports_vision: bool = False
    notes: str = ""

    @property
    def requires_key(self) -> bool:
        return self.env_var is not None

    @property
    def default_model(self) -> str:
        return self.default_models[0] if self.default_models else ""


# ---------------------------------------------------------------------------
# The registry. Models are sensible defaults the user can override at setup.
# ---------------------------------------------------------------------------

_PROVIDERS: list[ProviderInfo] = [
    ProviderInfo(
        id="mock", display_name="Mock (offline, no API key)", kind=KIND_MOCK,
        default_models=["mock"], supports_tools=True, supports_vision=True,
        notes="Deterministic offline planner + mock vision. The default.",
    ),
    ProviderInfo(
        id="openai", display_name="OpenAI", kind=KIND_NATIVE_OPENAI,
        default_models=["gpt-4o-mini", "gpt-4o", "o4-mini"],
        env_var="OPENAI_API_KEY", litellm_prefix="", supports_vision=True,
    ),
    ProviderInfo(
        id="anthropic", display_name="Anthropic (Claude)", kind=KIND_NATIVE_ANTHROPIC,
        default_models=["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        env_var="ANTHROPIC_API_KEY", litellm_prefix="anthropic/", supports_vision=True,
    ),
    ProviderInfo(
        id="gemini", display_name="Google Gemini", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
        env_var="GEMINI_API_KEY",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        litellm_prefix="gemini/", supports_vision=True,
    ),
    ProviderInfo(
        id="vertex", display_name="Google Vertex AI", kind=KIND_LITELLM_ONLY,
        default_models=["gemini-1.5-pro"], env_var=None,
        litellm_prefix="vertex_ai/", supports_vision=True,
        notes="Uses Google Cloud ADC credentials; via LiteLLM.",
    ),
    ProviderInfo(
        id="azure", display_name="Azure OpenAI", kind=KIND_LITELLM_ONLY,
        default_models=["gpt-4o-mini", "gpt-4o"], env_var="AZURE_API_KEY",
        needs_base_url=True, litellm_prefix="azure/", supports_vision=True,
        notes="Set base_url to your Azure endpoint; via LiteLLM.",
    ),
    ProviderInfo(
        id="bedrock", display_name="AWS Bedrock", kind=KIND_LITELLM_ONLY,
        default_models=["anthropic.claude-3-5-sonnet-20240620-v1:0"], env_var=None,
        litellm_prefix="bedrock/", supports_vision=True,
        notes="Uses AWS credentials (env/role); via LiteLLM.",
    ),
    ProviderInfo(
        id="mistral", display_name="Mistral AI", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["mistral-large-latest", "mistral-small-latest"],
        env_var="MISTRAL_API_KEY", default_base_url="https://api.mistral.ai/v1",
        litellm_prefix="mistral/",
    ),
    ProviderInfo(
        id="cohere", display_name="Cohere", kind=KIND_LITELLM_ONLY,
        default_models=["command-r-plus", "command-r"], env_var="COHERE_API_KEY",
        litellm_prefix="cohere/",
    ),
    ProviderInfo(
        id="groq", display_name="Groq", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        env_var="GROQ_API_KEY", default_base_url="https://api.groq.com/openai/v1",
        litellm_prefix="groq/",
    ),
    ProviderInfo(
        id="together", display_name="Together AI", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["meta-llama/Llama-3.3-70B-Instruct-Turbo"],
        env_var="TOGETHER_API_KEY", default_base_url="https://api.together.xyz/v1",
        litellm_prefix="together_ai/",
    ),
    ProviderInfo(
        id="openrouter", display_name="OpenRouter", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["openrouter/auto", "anthropic/claude-3.5-sonnet"],
        env_var="OPENROUTER_API_KEY", default_base_url="https://openrouter.ai/api/v1",
        litellm_prefix="openrouter/", supports_vision=True,
    ),
    ProviderInfo(
        id="deepseek", display_name="DeepSeek", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["deepseek-chat", "deepseek-reasoner"],
        env_var="DEEPSEEK_API_KEY", default_base_url="https://api.deepseek.com",
        litellm_prefix="deepseek/",
    ),
    ProviderInfo(
        id="xai", display_name="xAI (Grok)", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["grok-2-latest", "grok-2-vision-latest"],
        env_var="XAI_API_KEY", default_base_url="https://api.x.ai/v1",
        litellm_prefix="xai/", supports_vision=True,
    ),
    ProviderInfo(
        id="perplexity", display_name="Perplexity", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["llama-3.1-sonar-large-128k-online"],
        env_var="PERPLEXITY_API_KEY", default_base_url="https://api.perplexity.ai",
        litellm_prefix="perplexity/", supports_tools=False,
    ),
    ProviderInfo(
        id="fireworks", display_name="Fireworks AI", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["accounts/fireworks/models/llama-v3p3-70b-instruct"],
        env_var="FIREWORKS_API_KEY",
        default_base_url="https://api.fireworks.ai/inference/v1",
        litellm_prefix="fireworks_ai/",
    ),
    ProviderInfo(
        id="ollama", display_name="Ollama (local)", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["llama3.2", "qwen2.5", "mistral"], env_var=None,
        needs_base_url=True, default_base_url="http://localhost:11434/v1",
        litellm_prefix="ollama/", notes="Local; usually no API key.",
    ),
    ProviderInfo(
        id="lmstudio", display_name="LM Studio (local)", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["local-model"], env_var=None, needs_base_url=True,
        default_base_url="http://localhost:1234/v1", litellm_prefix="openai/",
        notes="Local OpenAI-compatible server.",
    ),
    ProviderInfo(
        id="vllm", display_name="vLLM (self-hosted)", kind=KIND_OPENAI_COMPATIBLE,
        default_models=["meta-llama/Llama-3.1-8B-Instruct"], env_var=None,
        needs_base_url=True, default_base_url="http://localhost:8000/v1",
        litellm_prefix="hosted_vllm/", notes="Self-hosted OpenAI-compatible server.",
    ),
    ProviderInfo(
        id="custom", display_name="Custom (any OpenAI-compatible endpoint)",
        kind=KIND_OPENAI_COMPATIBLE, default_models=["gpt-3.5-turbo"], env_var=None,
        needs_base_url=True, litellm_prefix="openai/",
        notes="Bring your own base_url (+ optional JARVIS_LLM_API_KEY).",
    ),
]

_BY_ID: dict[str, ProviderInfo] = {p.id: p for p in _PROVIDERS}


def all_providers() -> list[ProviderInfo]:
    return list(_PROVIDERS)


def provider_ids() -> list[str]:
    return [p.id for p in _PROVIDERS]


def get_provider(provider_id: Optional[str]) -> Optional[ProviderInfo]:
    if not provider_id:
        return None
    return _BY_ID.get(provider_id.strip().lower())


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


@dataclass
class ResolvedLLM:
    provider_id: str
    kind: str
    model: str
    litellm_model: str
    base_url: Optional[str]
    api_key: Optional[str]
    env_var: Optional[str]
    requires_key: bool
    supports_tools: bool
    supports_vision: bool
    display_name: str

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


def _mock_resolved() -> ResolvedLLM:
    return ResolvedLLM(
        provider_id="mock", kind=KIND_MOCK, model="mock", litellm_model="mock",
        base_url=None, api_key=None, env_var=None, requires_key=False,
        supports_tools=True, supports_vision=True, display_name="Mock",
    )


def _resolve_model(info: ProviderInfo, config, env: Mapping[str, str]) -> str:
    # Precedence: generic JARVIS_MODEL (config.llm_model) -> provider-specific
    # (legacy openai/anthropic config or JARVIS_<ID>_MODEL) -> registry default.
    generic = getattr(config, "llm_model", None)
    if generic:
        return generic
    if info.id == "openai" and getattr(config, "openai_model", None):
        return config.openai_model
    if info.id == "anthropic" and getattr(config, "anthropic_model", None):
        return config.anthropic_model
    per = env.get(f"JARVIS_{info.id.upper()}_MODEL")
    if per:
        return per
    return info.default_model


def _resolve_key(info: ProviderInfo, config, env: Mapping[str, str]) -> Optional[str]:
    if info.env_var:
        val = env.get(info.env_var)
        if val:
            return val
    # Generic fallback key for any provider (handy for custom/self-hosted).
    return getattr(config, "llm_api_key", None) or env.get("JARVIS_LLM_API_KEY") or None


def _resolve_base_url(info: ProviderInfo, config, env: Mapping[str, str]) -> Optional[str]:
    # Per-provider override wins (so reconfiguring one provider can't break
    # another), then the generic JARVIS_LLM_BASE_URL, then registry default.
    per = env.get(f"JARVIS_{info.id.upper()}_BASE_URL")
    if per:
        return per
    explicit = getattr(config, "llm_base_url", None)
    if explicit:
        return explicit
    if info.id == "openai" and env.get("OPENAI_BASE_URL"):
        return env.get("OPENAI_BASE_URL")
    return info.default_base_url


def resolve(config, env: Optional[Mapping[str, str]] = None) -> ResolvedLLM:
    """Resolve a Config (+ environment) to a concrete provider/model/key/base_url."""
    if env is None:
        env = os.environ
    provider_id = (getattr(config, "llm_provider", None) or "mock").strip().lower()
    info = get_provider(provider_id)
    if info is None or info.kind == KIND_MOCK:
        return _mock_resolved()

    model = _resolve_model(info, config, env)
    api_key = _resolve_key(info, config, env)
    base_url = _resolve_base_url(info, config, env)
    litellm_model = f"{info.litellm_prefix}{model}" if info.litellm_prefix else model

    return ResolvedLLM(
        provider_id=info.id,
        kind=info.kind,
        model=model,
        litellm_model=litellm_model,
        base_url=base_url,
        api_key=api_key,
        env_var=info.env_var,
        requires_key=info.requires_key,
        supports_tools=info.supports_tools,
        supports_vision=info.supports_vision,
        display_name=info.display_name,
    )


def key_is_set(info: ProviderInfo, config=None, env: Optional[Mapping[str, str]] = None) -> bool:
    """True if an API key is stored/resolvable for this provider (for ``key_set``).

    Reflects whether a key *exists*, independent of whether the provider needs one:
    * providers with a conventional env var → that var is non-empty;
    * the generic ``custom`` provider → the generic ``JARVIS_LLM_API_KEY`` is set;
    * key-less providers (local/cloud-cred: ollama, vllm, bedrock, …) → always False.
    """
    if env is None:
        env = os.environ
    if info.env_var:
        return bool(env.get(info.env_var))
    if info.id == "custom":
        generic = (getattr(config, "llm_api_key", None) if config else None) or env.get(
            "JARVIS_LLM_API_KEY"
        )
        return bool(generic)
    return False


__all__ = [
    "ProviderInfo",
    "ResolvedLLM",
    "all_providers",
    "provider_ids",
    "get_provider",
    "resolve",
    "key_is_set",
    "KIND_MOCK",
    "KIND_NATIVE_OPENAI",
    "KIND_NATIVE_ANTHROPIC",
    "KIND_OPENAI_COMPATIBLE",
    "KIND_LITELLM_ONLY",
]
