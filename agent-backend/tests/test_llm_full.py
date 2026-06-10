"""Exhaustive LLM-layer tests: extractors, mock planner, and every provider
(OpenAI / Anthropic / Generic / LiteLLM) with SDKs + httpx mocked."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import jarvis_backend.agent.llm as M
from jarvis_backend import providers as P
from jarvis_backend.agent.llm import (
    AnthropicLLM,
    GenericOpenAILLM,
    ImageInput,
    LiteLLMProvider,
    LLMMessage,
    LLMResult,
    LLMUnavailable,
    MockLLM,
    OpenAILLM,
    ToolCall,
    ToolSpec,
    _anthropic_attach_images,
    _build_native,
    _openai_attach_images,
    _openai_tools_payload,
    _parse_openai_tool_calls,
    _to_anthropic_messages,
    _to_openai_message,
    create_llm,
    extract_city,
    extract_destination,
    extract_duration_seconds,
    extract_object_name,
    extract_search_query,
    extract_symbols,
    extract_target_lang,
    plan_tool_calls,
)
from jarvis_backend.config import Config

AVAILABLE = {
    "get_weather", "start_timer", "stop_timer", "get_time", "take_note", "list_notes",
    "set_reminder", "identify_object", "describe_view", "read_text", "translate_view",
    "translate_text", "remember_object", "find_object", "identify_sound", "web_search",
    "get_news", "get_stocks", "get_calendar", "navigate_to", "measure", "open_widget",
    "show_text",
}


def _names(text):
    calls, direct = plan_tool_calls(text, AVAILABLE)
    return [c.name for c in calls], direct


# --- extractors -------------------------------------------------------------


def test_extract_city_variants():
    assert extract_city("weather in tokyo") == "Tokyo"
    assert extract_city("weather in new york") == "New York"
    assert extract_city("weather berlin") == "Berlin"
    assert extract_city("weather in tokyo and london") == "Tokyo"  # cut at conjunction
    assert extract_city("weather in paris please") == "Paris"  # stop-trail removed
    assert extract_city("weather in someville") == "Someville"  # title-cased unknown
    assert extract_city("is it sunny in sydney") == "Sydney"  # known city anywhere
    assert extract_city("what's the temperature") == "San Francisco"  # default


def test_extract_duration_seconds():
    assert extract_duration_seconds("set a timer for 5 minutes") == 300
    assert extract_duration_seconds("2 hours and 30 minutes") == 2 * 3600 + 30 * 60
    assert extract_duration_seconds("90 seconds") == 90
    assert extract_duration_seconds("five minutes") == 300  # word number
    assert extract_duration_seconds("an hour") == 3600  # word number "an"
    assert extract_duration_seconds("xyz minutes") == 60  # unknown word -> default
    assert extract_duration_seconds("no duration here") == 60
    assert extract_duration_seconds("0 minutes") == 60  # zero -> default 60


def test_extract_target_lang():
    assert extract_target_lang("translate to french") == "french"
    assert extract_target_lang("translate this") == "spanish"


def test_extract_object_name_patterns():
    assert extract_object_name("where did i leave my keys?") == "keys"
    assert extract_object_name("where's my wallet?") == "wallet"
    assert extract_object_name("have you seen my phone?") == "phone"
    assert extract_object_name("find my glasses") == "glasses"
    assert extract_object_name("remember that my book is on the shelf") == "book"
    assert extract_object_name("this is my mug,") == "mug"
    assert extract_object_name("blah blah") == "it"


def test_extract_search_and_destination():
    assert extract_search_query("search for mars rovers") == "mars rovers"
    assert extract_search_query("look up python") == "python"
    assert extract_search_query("hello") == ""
    assert extract_destination("navigate to the kitchen") == "the kitchen"
    assert extract_destination("hello") == ""


def test_extract_symbols():
    assert extract_symbols("AAPL and TSLA") == ["AAPL", "TSLA"]
    assert extract_symbols("buy apple and tesla") == ["AAPL", "TSLA"]
    assert extract_symbols("the USD price of nothing") == ["AAPL", "TSLA", "NVDA"]


# --- plan_tool_calls --------------------------------------------------------


def test_plan_greeting_and_thanks():
    assert plan_tool_calls("hi jarvis", AVAILABLE) == ([], "Hello. Jarvis here — how can I help?")
    assert plan_tool_calls("thanks", AVAILABLE) == ([], "You're welcome.")


def test_plan_builtin_intents():
    assert _names("what's the weather in tokyo")[0] == ["get_weather"]
    assert _names("set a 5 minute timer")[0] == ["start_timer"]
    assert _names("stop the timer")[0] == ["stop_timer"]
    assert _names("what time is it")[0] == ["get_time"]
    assert _names("list my notes")[0] == ["list_notes"]
    assert _names("take a note buy milk")[0] == ["take_note"]
    assert _names("remind me to call mom")[0] == ["set_reminder"]


def test_plan_take_note_text_extraction():
    calls, _ = plan_tool_calls("take a note buy oat milk", AVAILABLE)
    assert calls[0].arguments["text"] == "buy oat milk"


def test_plan_perception_intents():
    assert "identify_object" in _names("what is this")[0]
    assert "describe_view" in _names("what do you see")[0]
    assert "read_text" in _names("read this")[0]
    assert "translate_view" in _names("translate this to french")[0]
    assert "translate_text" in _names("translate hello to spanish")[0]
    assert "remember_object" in _names("remember my keys are on the table")[0]
    assert "find_object" in _names("where did i leave my keys")[0]
    assert "identify_sound" in _names("what was that sound")[0]
    assert "web_search" in _names("search for mars")[0]
    assert "get_news" in _names("news about space")[0]
    assert "get_stocks" in _names("stock price for AAPL")[0]
    assert "get_calendar" in _names("what's on my calendar")[0]
    assert "navigate_to" in _names("navigate to the kitchen")[0]
    assert "measure" in _names("measure the desk")[0]


def test_plan_open_widget_and_fallback():
    assert _names("open the media player")[0] == ["open_widget"]
    assert _names("tell me a joke")[0] == ["show_text"]  # fallback panel
    # without show_text available -> a direct reply, no tools
    calls, direct = plan_tool_calls("tell me a joke", set())
    assert calls == [] and direct


def test_plan_respects_unavailable_tools():
    calls, _ = plan_tool_calls("what's the weather in tokyo", {"show_text"})
    assert [c.name for c in calls] == ["show_text"]  # weather not available -> fallback


# --- MockLLM ----------------------------------------------------------------


async def test_mock_plans_then_summarizes():
    mock = MockLLM()
    tools = [ToolSpec("get_weather", "w", {"type": "object", "properties": {}})]
    plan = await mock.complete([LLMMessage(role="user", content="weather in tokyo")], tools)
    assert plan.tool_calls and plan.tool_calls[0].name == "get_weather"

    final = await mock.complete(
        [
            LLMMessage(role="user", content="weather in tokyo"),
            LLMMessage(role="tool", content='{"speech": "It is 18C."}', tool_call_id="c1", name="get_weather"),
        ],
        tools,
    )
    assert final.content == "It is 18C."


async def test_mock_direct_reply_and_summarize_edge_cases():
    mock = MockLLM()
    res = await mock.complete([LLMMessage(role="user", content="hello")], [])
    assert "Hello" in (res.content or "")
    # tool messages with invalid json / no speech -> "Done."
    final = await mock.complete(
        [
            LLMMessage(role="user", content="x"),
            LLMMessage(role="tool", content="not json", tool_call_id="c", name="t"),
            LLMMessage(role="tool", content='{"no": "speech"}', tool_call_id="c2", name="t2"),
        ],
        [],
    )
    assert final.content == "Done."


async def test_mock_complete_no_user_message():
    # No user message + no tools -> the deterministic direct help reply.
    assert "I can help" in (await MockLLM().complete([], [])).content


# --- message + payload helpers ----------------------------------------------


def test_to_openai_message_shapes():
    asst = _to_openai_message(LLMMessage(role="assistant", tool_calls=[ToolCall("c1", "t", {"a": 1})]))
    assert asst["tool_calls"][0]["function"]["name"] == "t"
    tool = _to_openai_message(LLMMessage(role="tool", content="r", tool_call_id="c1", name="t"))
    assert tool == {"role": "tool", "tool_call_id": "c1", "content": "r"}
    plain = _to_openai_message(LLMMessage(role="user", content="hi"))
    assert plain == {"role": "user", "content": "hi"}


def test_openai_tools_payload_and_parse():
    payload = _openai_tools_payload([ToolSpec("t", "d", {"type": "object"})])
    assert payload[0]["function"]["name"] == "t"
    # dict form, bad-json args, dict args, sdk-object form, nameless skipped
    calls = _parse_openai_tool_calls(
        [
            {"id": "1", "function": {"name": "a", "arguments": '{"x":1}'}},
            {"id": "2", "function": {"name": "b", "arguments": "{bad"}},
            {"id": "3", "function": {"name": "c", "arguments": {"y": 2}}},
            SimpleNamespace(id="4", function=SimpleNamespace(name="d", arguments=None)),
            {"id": "5", "function": {"name": "", "arguments": "{}"}},
        ]
    )
    assert [c.name for c in calls] == ["a", "b", "c", "d"]
    assert calls[0].arguments == {"x": 1}
    assert calls[1].arguments == {}  # bad json -> {}
    assert calls[2].arguments == {"y": 2}
    assert _parse_openai_tool_calls(None) == []


def test_openai_attach_images():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]
    _openai_attach_images(msgs, [ImageInput(b64="QQ==", media_type="image/png")])
    blocks = msgs[1]["content"]
    assert blocks[0] == {"type": "text", "text": "hi"}
    assert blocks[1]["image_url"]["url"].startswith("data:image/png;base64,QQ==")


def test_anthropic_message_conversion_and_images():
    msgs = [
        LLMMessage(role="system", content="sys"),
        LLMMessage(role="user", content="hi"),
        LLMMessage(role="assistant", content="ok", tool_calls=[ToolCall("c1", "t", {"a": 1})]),
        LLMMessage(role="tool", content="result", tool_call_id="c1", name="t"),
        LLMMessage(role="assistant"),  # empty -> placeholder text block
    ]
    out = _to_anthropic_messages(msgs)
    assert out[0]["role"] == "user" and out[0]["content"][0]["text"] == "hi"
    assert any(b["type"] == "tool_use" for b in out[1]["content"])
    assert out[2]["content"][0]["type"] == "tool_result"
    assert out[3]["content"] == [{"type": "text", "text": ""}]
    _anthropic_attach_images(out, [ImageInput(b64="QQ==")])
    # appended to the last user message (the tool_result one)
    assert any(b.get("type") == "image" for b in out[-2]["content"]) or any(
        b.get("type") == "image" for m in out for b in (m["content"] if isinstance(m["content"], list) else [])
    )


def test_anthropic_attach_images_wraps_string_content():
    msgs = [{"role": "user", "content": "hi"}]
    _anthropic_attach_images(msgs, [ImageInput(b64="QQ==")])
    assert msgs[0]["content"][0] == {"type": "text", "text": "hi"}
    assert msgs[0]["content"][1]["type"] == "image"


# --- OpenAILLM (SDK mocked) -------------------------------------------------


def _install_fake_openai(monkeypatch, capture):
    class _Completions:
        async def create(self, **kwargs):
            capture.update(kwargs)
            msg = SimpleNamespace(
                content="hi from openai",
                tool_calls=[SimpleNamespace(id="c1", function=SimpleNamespace(name="get_weather", arguments='{"city":"Tokyo"}'))],
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class AsyncOpenAI:
        def __init__(self, **kwargs):
            capture["init"] = kwargs
            self.chat = _Chat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AsyncOpenAI))


def test_openai_requires_key():
    with pytest.raises(LLMUnavailable):
        OpenAILLM("gpt-4o", None)


def test_openai_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)  # import fails
    with pytest.raises(LLMUnavailable):
        OpenAILLM("gpt-4o", "sk-1")


async def test_openai_complete_with_tools_and_images(monkeypatch):
    capture = {}
    _install_fake_openai(monkeypatch, capture)
    llm = OpenAILLM("gpt-4o", "sk-1", base_url="http://x/v1")
    res = await llm.complete(
        [LLMMessage(role="user", content="weather?")],
        [ToolSpec("get_weather", "w", {"type": "object"})],
        images=[ImageInput(b64="QQ==")],
    )
    assert res.content == "hi from openai"
    assert res.tool_calls[0].name == "get_weather"
    assert capture["init"]["base_url"] == "http://x/v1"
    assert capture["tool_choice"] == "auto"
    assert isinstance(capture["messages"][-1]["content"], list)  # image attached


# --- AnthropicLLM (SDK mocked) ----------------------------------------------


def _install_fake_anthropic(monkeypatch, capture):
    class _Messages:
        async def create(self, **kwargs):
            capture.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="text", text="claude says hi"),
                    SimpleNamespace(type="tool_use", id="t1", name="get_weather", input={"city": "Tokyo"}),
                ]
            )

    class AsyncAnthropic:
        def __init__(self, **kwargs):
            capture["init"] = kwargs
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=AsyncAnthropic))


def test_anthropic_requires_key():
    with pytest.raises(LLMUnavailable):
        AnthropicLLM("claude", None)


def test_anthropic_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(LLMUnavailable):
        AnthropicLLM("claude", "ak-1")


async def test_anthropic_complete(monkeypatch):
    capture = {}
    _install_fake_anthropic(monkeypatch, capture)
    llm = AnthropicLLM("claude-3-5", "ak-1", base_url="http://a")
    res = await llm.complete(
        [LLMMessage(role="system", content="sys"), LLMMessage(role="user", content="weather?")],
        [ToolSpec("get_weather", "w", {"type": "object"})],
        images=[ImageInput(b64="QQ==")],
    )
    assert res.content == "claude says hi"
    assert res.tool_calls[0].name == "get_weather"
    assert capture["system"] == "sys"
    assert capture["init"]["base_url"] == "http://a"


# --- GenericOpenAILLM -------------------------------------------------------


def test_generic_requires_base_url():
    with pytest.raises(LLMUnavailable):
        GenericOpenAILLM("custom", "m", "k", None)


def test_generic_build_request_vision():
    llm = GenericOpenAILLM("xai", "grok", "k", "http://x/v1", supports_vision=True)
    req = llm.build_request([LLMMessage(role="user", content="hi")], [], [ImageInput(b64="QQ==")])
    assert isinstance(req["json"]["messages"][0]["content"], list)


def test_generic_parse_empty_choices():
    assert GenericOpenAILLM.parse_response({}).content is None


async def test_generic_complete_raises_for_status(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            raise RuntimeError("http 500")

        def json(self):
            return {}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(M, "httpx", SimpleNamespace(AsyncClient=lambda *a, **k: _Client()))
    llm = GenericOpenAILLM("groq", "m", "k", "http://g/v1")
    with pytest.raises(RuntimeError):
        await llm.complete([LLMMessage(role="user", content="hi")], [])


# --- LiteLLMProvider --------------------------------------------------------


def _resolved(provider_id="gemini", **over):
    base = dict(
        provider_id=provider_id, kind=P.KIND_OPENAI_COMPATIBLE, model="m", litellm_model="gemini/m",
        base_url="http://b", api_key="k", env_var="GEMINI_API_KEY", requires_key=True,
        supports_tools=True, supports_vision=True, display_name="Gemini",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_litellm_missing_dep(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", None)
    with pytest.raises(LLMUnavailable):
        LiteLLMProvider(_resolved())


def test_litellm_requires_key(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=None))
    with pytest.raises(LLMUnavailable):
        LiteLLMProvider(_resolved(api_key=None))


async def test_litellm_complete_object_and_dict(monkeypatch):
    captured = {}

    async def acompletion_obj(**kwargs):
        captured.update(kwargs)
        msg = SimpleNamespace(content="lite hi", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=acompletion_obj))
    llm = LiteLLMProvider(_resolved())
    res = await llm.complete(
        [LLMMessage(role="user", content="hi")],
        [ToolSpec("t", "d", {"type": "object"})],
        images=[ImageInput(b64="QQ==")],
    )
    assert res.content == "lite hi"
    assert captured["api_key"] == "k" and captured["api_base"] == "http://b"
    assert captured["tools"][0]["function"]["name"] == "t"

    # dict-like ModelResponse -> AttributeError fallback path
    async def acompletion_dict(**kwargs):
        return {"choices": [{"message": {"content": "dict hi", "tool_calls": None}}]}

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=acompletion_dict))
    llm2 = LiteLLMProvider(_resolved())
    res2 = await llm2.complete([LLMMessage(role="user", content="hi")], [])
    assert res2.content == "dict hi"


# --- _build_native + create_llm ---------------------------------------------


def test_build_native_paths(monkeypatch):
    capture = {}
    _install_fake_openai(monkeypatch, capture)
    _install_fake_anthropic(monkeypatch, capture)
    assert isinstance(_build_native(_resolved("openai", kind=P.KIND_NATIVE_OPENAI)), OpenAILLM)
    assert isinstance(_build_native(_resolved("anthropic", kind=P.KIND_NATIVE_ANTHROPIC)), AnthropicLLM)
    assert isinstance(_build_native(_resolved("groq", kind=P.KIND_OPENAI_COMPATIBLE)), GenericOpenAILLM)


def test_build_native_openai_compatible_requires_key():
    with pytest.raises(LLMUnavailable):
        _build_native(_resolved("groq", kind=P.KIND_OPENAI_COMPATIBLE, requires_key=True, api_key=None))


def test_build_native_unknown_kind():
    with pytest.raises(LLMUnavailable):
        _build_native(_resolved("vertex", kind="weird-kind"))


def test_create_llm_native_success(monkeypatch):
    capture = {}
    _install_fake_openai(monkeypatch, capture)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1")
    llm = create_llm(Config(llm_provider="openai"))
    assert isinstance(llm, OpenAILLM)


async def test_create_llm_prefers_litellm_when_requested(monkeypatch):
    async def acompletion(**kwargs):
        return {"choices": [{"message": {"content": "x"}}]}

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=acompletion))
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    llm = create_llm(Config(llm_provider="gemini", use_litellm=True))
    assert isinstance(llm, LiteLLMProvider)
