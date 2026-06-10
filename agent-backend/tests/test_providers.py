"""Multi-provider registry + resolution + generic OpenAI-compatible provider."""

from __future__ import annotations

from types import SimpleNamespace

import jarvis_backend.agent.llm as llm_mod
from jarvis_backend import providers as P
from jarvis_backend.agent.llm import (
    GenericOpenAILLM,
    LLMMessage,
    MockLLM,
    ToolSpec,
    create_llm,
)
from jarvis_backend.config import Config

# Env vars that could leak from the host and skew resolution tests.
_KEY_VARS = [
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
    "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "XAI_API_KEY", "MISTRAL_API_KEY",
    "TOGETHER_API_KEY", "PERPLEXITY_API_KEY", "FIREWORKS_API_KEY", "AZURE_API_KEY",
    "COHERE_API_KEY", "JARVIS_LLM_API_KEY", "JARVIS_MODEL", "JARVIS_LLM_BASE_URL",
    "JARVIS_USE_LITELLM", "OPENAI_BASE_URL",
]


def _clean_env(monkeypatch):
    for v in _KEY_VARS:
        monkeypatch.delenv(v, raising=False)


# --- registry ---------------------------------------------------------------


def test_registry_lists_major_providers():
    ids = set(P.provider_ids())
    expected = {
        "mock", "openai", "anthropic", "gemini", "vertex", "azure", "bedrock",
        "mistral", "cohere", "groq", "together", "openrouter", "deepseek", "xai",
        "perplexity", "fireworks", "ollama", "lmstudio", "vllm", "custom",
    }
    assert expected <= ids
    assert len(ids) >= 18


def test_providers_well_formed():
    for p in P.all_providers():
        assert p.id and p.display_name and p.kind
        if p.kind != P.KIND_MOCK:
            assert p.default_models, f"{p.id} has no default model"
        if p.kind == P.KIND_OPENAI_COMPATIBLE:
            # Either a default base URL or it explicitly needs one.
            assert p.default_base_url or p.needs_base_url


# --- resolution -------------------------------------------------------------


def test_resolve_mock_default(monkeypatch):
    _clean_env(monkeypatch)
    r = P.resolve(Config(), env={})
    assert r.provider_id == "mock" and r.kind == P.KIND_MOCK


def test_resolve_key_from_provider_env(monkeypatch):
    r = P.resolve(Config(llm_provider="groq"), env={"GROQ_API_KEY": "gk-1"})
    assert r.provider_id == "groq"
    assert r.api_key == "gk-1"
    assert r.base_url == "https://api.groq.com/openai/v1"
    assert r.kind == P.KIND_OPENAI_COMPATIBLE


def test_resolve_key_precedence_provider_over_generic():
    cfg = Config(llm_provider="openai", llm_api_key="generic-key")
    r = P.resolve(cfg, env={"OPENAI_API_KEY": "sk-real"})
    assert r.api_key == "sk-real"  # provider env var wins over generic


def test_resolve_generic_key_fallback():
    cfg = Config(llm_provider="custom", llm_base_url="http://host:1234/v1", llm_api_key="gen")
    r = P.resolve(cfg, env={})
    assert r.api_key == "gen"
    assert r.base_url == "http://host:1234/v1"


def test_resolve_model_precedence():
    # generic JARVIS_MODEL (config.llm_model) wins
    r = P.resolve(Config(llm_provider="groq", llm_model="my-model"), env={})
    assert r.model == "my-model"
    # else per-provider env
    r2 = P.resolve(Config(llm_provider="groq"), env={"JARVIS_GROQ_MODEL": "g-model"})
    assert r2.model == "g-model"
    # else registry default
    r3 = P.resolve(Config(llm_provider="groq"), env={})
    assert r3.model == P.get_provider("groq").default_model


def test_resolve_base_url_per_provider_override():
    r = P.resolve(Config(llm_provider="ollama"), env={"JARVIS_OLLAMA_BASE_URL": "http://box:9/v1"})
    assert r.base_url == "http://box:9/v1"


def test_resolve_litellm_model_prefix():
    r = P.resolve(Config(llm_provider="gemini"), env={"GEMINI_API_KEY": "g"})
    assert r.litellm_model == "gemini/" + r.model


# --- create_llm -------------------------------------------------------------


def test_create_llm_mock_when_no_provider(monkeypatch):
    _clean_env(monkeypatch)
    assert isinstance(create_llm(Config()), MockLLM)


def test_create_llm_falls_back_to_mock_without_key(monkeypatch):
    _clean_env(monkeypatch)
    # openai selected but no key + (litellm not installed) -> mock, never crash.
    assert isinstance(create_llm(Config(llm_provider="openai")), MockLLM)


def test_create_llm_unknown_provider_is_mock(monkeypatch):
    _clean_env(monkeypatch)
    assert isinstance(create_llm(Config(llm_provider="totally-made-up")), MockLLM)


def test_create_llm_generic_openai_compatible(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gk-1")
    llm = create_llm(Config(llm_provider="groq"))
    assert isinstance(llm, GenericOpenAILLM)
    assert llm.name == "groq"
    assert llm.model == P.get_provider("groq").default_model
    assert llm._base_url == "https://api.groq.com/openai/v1"


def test_create_llm_litellm_only_without_litellm_is_mock(monkeypatch):
    _clean_env(monkeypatch)
    # bedrock is litellm_only; litellm isn't installed in the test env -> mock.
    assert isinstance(create_llm(Config(llm_provider="bedrock")), MockLLM)


# --- generic provider request building / parsing ----------------------------


def test_generic_build_request_shape():
    llm = GenericOpenAILLM("groq", "llama-3.3-70b-versatile", "gk-1", "https://api.groq.com/openai/v1")
    req = llm.build_request(
        [LLMMessage(role="user", content="hi")],
        [ToolSpec("get_weather", "Weather", {"type": "object", "properties": {}})],
    )
    assert req["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer gk-1"
    body = req["json"]
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["messages"][0]["content"] == "hi"
    assert body["tools"][0]["function"]["name"] == "get_weather"
    assert body["tool_choice"] == "auto"


def test_generic_no_key_no_auth_header():
    llm = GenericOpenAILLM("ollama", "llama3.2", None, "http://localhost:11434/v1")
    req = llm.build_request([LLMMessage(role="user", content="hi")], [])
    assert "Authorization" not in req["headers"]
    assert "tools" not in req["json"]


def test_generic_parse_response_tool_calls():
    data = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {"id": "c1", "function": {"name": "get_weather", "arguments": '{"city": "Tokyo"}'}}
                    ],
                }
            }
        ]
    }
    res = GenericOpenAILLM.parse_response(data)
    assert res.content is None
    assert res.tool_calls[0].name == "get_weather"
    assert res.tool_calls[0].arguments == {"city": "Tokyo"}


async def test_generic_complete_mocks_http(monkeypatch):
    captured: dict = {}
    payload = {"choices": [{"message": {"content": "hello from groq", "tool_calls": []}}]}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(llm_mod, "httpx", SimpleNamespace(AsyncClient=_Client))
    llm = GenericOpenAILLM("groq", "llama-3.3-70b-versatile", "gk-1", "https://api.groq.com/openai/v1")
    res = await llm.complete([LLMMessage(role="user", content="hi")], [])
    assert res.content == "hello from groq"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer gk-1"
