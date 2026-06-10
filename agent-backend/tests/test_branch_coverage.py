"""Branch/line mop-up across modules to push toward full coverage."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import jarvis_backend.agent.llm as M
from jarvis_backend import logging_setup
from jarvis_backend import providers as P
from jarvis_backend.agent.llm import (
    AnthropicLLM,
    ImageInput,
    LiteLLMProvider,
    LLMMessage,
    OpenAILLM,
    ToolSpec,
    extract_city,
    _anthropic_attach_images,
    _openai_attach_images,
)
from jarvis_backend.agent.memory import ConversationMemory, EpisodicMemory, LongTermStore
from jarvis_backend.agent.tools import builtins as BT
from jarvis_backend.agent.tools import perception_tools as PT
from jarvis_backend.agent.state import SessionState
from jarvis_backend.agent.tools.base import ToolContext
from jarvis_backend.agent.trace import Tracer
from jarvis_backend.catalog import CatalogError, WidgetCatalog
from jarvis_backend.config import Config
from jarvis_backend.perception import vision as V
from jarvis_backend.perception.buffer import PerceptionBuffer
from jarvis_backend.skills.loader import Skill, SkillRegistry


def _ctx(tmp_path, episodic=True, objects=None):
    s = SessionState(session_id="S")
    if objects is not None:
        s.perception.set_scene_objects({"objects": objects})
    lt = LongTermStore(tmp_path / "m.json")
    return ToolContext(config=Config(data_dir=Path(tmp_path)), session=s, catalog=WidgetCatalog.builtin(),
                       longterm=lt, episodic=EpisodicMemory(lt) if episodic else None)


# --- llm line/branch --------------------------------------------------------


def test_extract_city_anywhere_loop():
    assert extract_city("tokyo weather today") == "Tokyo"  # known city, not after in/weather


def _fake_openai(monkeypatch, capture):
    class _Completions:
        async def create(self, **kwargs):
            capture.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None))])

    class AsyncOpenAI:
        def __init__(self, **kwargs):
            capture["init"] = kwargs
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AsyncOpenAI))


async def test_openai_no_base_no_images_no_tools(monkeypatch):
    capture = {}
    _fake_openai(monkeypatch, capture)
    llm = OpenAILLM("gpt-4o", "sk-1")  # no base_url
    await llm.complete([LLMMessage(role="user", content="hi")], [])  # no tools, no images
    assert "base_url" not in capture["init"]
    assert "tools" not in capture
    assert capture["messages"][-1]["content"] == "hi"  # not a block list


def _fake_anthropic(monkeypatch, capture, blocks=None):
    class _Messages:
        async def create(self, **kwargs):
            capture.update(kwargs)
            return SimpleNamespace(content=blocks or [SimpleNamespace(type="text", text="hi")])

    class AsyncAnthropic:
        def __init__(self, **kwargs):
            capture["init"] = kwargs
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=AsyncAnthropic))


async def test_anthropic_no_base_no_images_and_other_block(monkeypatch):
    capture = {}
    _fake_anthropic(monkeypatch, capture, blocks=[SimpleNamespace(type="thinking", text="…")])  # neither text nor tool_use
    llm = AnthropicLLM("claude", "ak-1")  # no base_url
    res = await llm.complete([LLMMessage(role="user", content="hi")], [])  # no tools/images
    assert "base_url" not in capture["init"]
    assert res.content is None and res.tool_calls == []


def _resolved(**over):
    base = dict(provider_id="custom", kind=P.KIND_OPENAI_COMPATIBLE, model="m", litellm_model="m",
                base_url=None, api_key=None, env_var=None, requires_key=False,
                supports_tools=True, supports_vision=False, display_name="C")
    base.update(over)
    return SimpleNamespace(**base)


async def test_litellm_no_key_no_base_no_tools(monkeypatch):
    captured = {}

    async def acompletion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="x", tool_calls=None))])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=acompletion))
    llm = LiteLLMProvider(_resolved())  # requires_key False, no key/base
    await llm.complete([LLMMessage(role="user", content="hi")], [])
    assert "api_key" not in captured and "api_base" not in captured and "tools" not in captured


def test_attach_images_no_user_message():
    msgs = [{"role": "system", "content": "s"}]
    _openai_attach_images(msgs, [ImageInput(b64="QQ==")])  # no user -> no-op
    assert msgs == [{"role": "system", "content": "s"}]
    _anthropic_attach_images(msgs, [ImageInput(b64="QQ==")])  # no user -> no-op
    assert msgs == [{"role": "system", "content": "s"}]


# --- memory -----------------------------------------------------------------


def test_heuristic_summary_includes_tool_lines():
    out = ConversationMemory._heuristic_summary(
        [LLMMessage(role="tool", name="get_weather", content="{}"),
         LLMMessage(role="assistant", content="hi"),
         LLMMessage(role="user", content="hey")],
        "",
    )
    assert "Tool get_weather ran" in out and "User said" in out


def test_recall_object_fuzzy(tmp_path):
    em = EpisodicMemory(LongTermStore(tmp_path / "e.json"))
    em.remember_object("my keys", position=[1, 1, 1])
    assert em.recall_object("house keys") is not None  # fuzzy substring match


def test_heuristic_summary_skips_other_roles():
    out = ConversationMemory._heuristic_summary(
        [LLMMessage(role="system", content="ignored"),  # neither user/assistant/tool -> skipped
         LLMMessage(role="user", content="hi")],
        "",
    )
    assert "ignored" not in out and "User said" in out


def test_plan_read_text_skipped_when_notes_present():
    from jarvis_backend.agent.llm import plan_tool_calls

    avail = {"read_text", "list_notes"}
    names = [c.name for c in plan_tool_calls("read this note", avail)[0]]
    assert "read_text" not in names  # "notes" keyword suppresses OCR read


# --- skills -----------------------------------------------------------------


def test_skill_registry_constructed_with_skills():
    reg = SkillRegistry([Skill(name="s", description="d", path=Path("p"), metadata={"agent": "r"})])
    assert reg.get("s") is not None and reg.for_agent("r")


# --- builtins ---------------------------------------------------------------


def test_stop_timer_explicit_ref_not_last(tmp_path):
    ctx = _ctx(tmp_path)
    first = BT._start_timer({"duration_seconds": 60}, ctx).data["timer_ref"]
    BT._start_timer({"duration_seconds": 60}, ctx)  # last_timer_ref now points to the 2nd
    stopped = BT._stop_timer({"timer_ref": first}, ctx)  # stop the first by ref
    assert stopped.data["stopped"] is True
    assert ctx.session.store["last_timer_ref"] != first  # last untouched


def test_open_widget_anchor_only_and_position_only(tmp_path):
    ctx = _ctx(tmp_path)
    a = BT._open_widget({"widget_type": "panel", "anchor": "head"}, ctx)
    assert a.directives[0].transform == {"anchor": "head"}
    p = BT._open_widget({"widget_type": "panel", "position": [0, 1, 1]}, ctx)
    assert p.directives[0].transform == {"position": [0, 1, 1]}


# --- perception tools -------------------------------------------------------


def test_remember_seen_skips_label_less_objects(tmp_path):
    ctx = _ctx(tmp_path, objects=[{"position": [0, 0, 1]}])  # no label
    PT._describe_view({}, ctx)  # must not crash; the label-less object is skipped
    assert ctx.episodic.seen_objects() == {}


# --- perception buffer ------------------------------------------------------


def test_add_vision_frame_raw_with_existing_data():
    b = PerceptionBuffer()
    rec = b.add_vision_frame({"frame_id": "x", "data": "QUJD"}, raw=b"abc")
    assert rec.size_bytes == 3 and rec.data_b64 == "QUJD"  # kept payload b64, used raw size


# --- vision focus -----------------------------------------------------------


def test_focus_object_hit_id_no_match_then_point():
    objs = [{"label": "a", "position": [0, 0, 0]}, {"label": "b", "position": [9, 9, 9]}]
    # hit_object_id present but matches nothing -> falls through to hit_point
    near = V.focus_object({"objects": objs, "gaze": {"hit_object_id": "X", "hit_point": [0.1, 0, 0]}})
    assert near["label"] == "a"
    # hit_point present but no placed objects -> first object
    unplaced = [{"label": "c"}]
    assert V.focus_object({"objects": unplaced, "gaze": {"hit_point": [1, 2, 3]}})["label"] == "c"


# --- catalog validate skip non-dict prop schema -----------------------------


def test_validate_skips_non_dict_property_schema():
    cat = WidgetCatalog({"widgets": {"w": {"prefab_id": "W", "props_schema": {
        "type": "object", "properties": {"a": "string-shorthand-not-a-dict"}}}}})
    cat.validate("w", {"a": "anything"})  # property schema isn't a dict -> skipped, no raise


# --- logging json without exc ----------------------------------------------


def test_json_formatter_without_exc():
    rec = logging.LogRecord("n", logging.INFO, __file__, 1, "plain", (), None)
    import json

    data = json.loads(logging_setup._JsonFormatter().format(rec))
    assert "exc" not in data and data["msg"] == "plain"


# --- trace ring eviction ----------------------------------------------------


def test_tracer_ring_evicts_oldest():
    tr = Tracer(emit=None, enabled=True, capacity=2)
    tr.start("P1", "g")
    tr.start("P2", "g")
    tr.start("P3", "g")  # evicts P1
    assert tr.get("P1") is None
    assert tr.get("P2") is not None and tr.get("P3") is not None


# --- provider client caching (second call reuses the client) ----------------


async def test_openai_client_is_cached(monkeypatch):
    capture = {"inits": 0}

    class _Completions:
        async def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None))])

    class AsyncOpenAI:
        def __init__(self, **kwargs):
            capture["inits"] += 1
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=AsyncOpenAI))
    llm = OpenAILLM("gpt-4o", "sk-1")
    await llm.complete([LLMMessage(role="user", content="hi")], [])
    await llm.complete([LLMMessage(role="user", content="again")], [])
    assert capture["inits"] == 1  # client built once, reused thereafter


async def test_anthropic_client_is_cached(monkeypatch):
    capture = {"inits": 0}

    class _Messages:
        async def create(self, **kwargs):
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="hi")])

    class AsyncAnthropic:
        def __init__(self, **kwargs):
            capture["inits"] += 1
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=AsyncAnthropic))
    llm = AnthropicLLM("claude", "ak-1")
    await llm.complete([LLMMessage(role="user", content="hi")], [])
    await llm.complete([LLMMessage(role="user", content="again")], [])
    assert capture["inits"] == 1


# --- catalog: widgets neither dict nor list + property schema w/o type -------


def test_catalog_widgets_non_collection():
    cat = WidgetCatalog({"widgets": "not a collection"})
    assert cat.names() == []


def test_validate_property_dict_schema_without_type_or_enum():
    cat = WidgetCatalog({"widgets": {"w": {"prefab_id": "W", "props_schema": {
        "type": "object", "properties": {"a": {}}}}}})  # prop schema dict, no type/enum
    cat.validate("w", {"a": 12345})  # accepted (no constraints)
