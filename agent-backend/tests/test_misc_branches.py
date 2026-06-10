"""Targeted branch coverage: providers, memory, persona, state, trace,
perception-tool fallbacks, and a couple of planner edges."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend import protocol
from jarvis_backend import providers as P
from jarvis_backend.agent.agent_memory import PerAgentMemory
from jarvis_backend.agent.llm import LLMMessage, MockLLM, plan_tool_calls
from jarvis_backend.agent.memory import EpisodicMemory, LongTermStore
from jarvis_backend.agent.persona import build_system_prompt
from jarvis_backend.agent.state import SessionState
from jarvis_backend.agent.tools import perception_tools as PT
from jarvis_backend.agent.tools.base import ToolContext
from jarvis_backend.agent.trace import Tracer
from jarvis_backend.catalog import WidgetCatalog
from jarvis_backend.config import Config
from jarvis_backend.protocol import HoloObject, Transform


# --- providers --------------------------------------------------------------


def test_get_provider_none_and_normalized():
    assert P.get_provider(None) is None
    assert P.get_provider("  OpenAI ").id == "openai"
    assert P.get_provider("zzz") is None


def test_resolved_has_key():
    assert P.resolve(Config(llm_provider="groq"), env={"GROQ_API_KEY": "k"}).has_key is True
    assert P.resolve(Config(llm_provider="groq"), env={}).has_key is False


def test_resolve_model_provider_specific():
    r = P.resolve(Config(llm_provider="openai", openai_model="gpt-x"), env={"OPENAI_API_KEY": "k"})
    assert r.model == "gpt-x"
    r2 = P.resolve(Config(llm_provider="anthropic", anthropic_model="claude-x"), env={"ANTHROPIC_API_KEY": "k"})
    assert r2.model == "claude-x"


def test_resolve_base_url_openai_env():
    r = P.resolve(Config(llm_provider="openai"), env={"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": "http://x/v1"})
    assert r.base_url == "http://x/v1"


def test_key_is_set_variants():
    assert P.key_is_set(P.get_provider("openai"), env={"OPENAI_API_KEY": "k"}) is True
    assert P.key_is_set(P.get_provider("openai"), env={}) is False
    assert P.key_is_set(P.get_provider("custom"), Config(llm_api_key="g"), env={}) is True
    assert P.key_is_set(P.get_provider("custom"), None, env={"JARVIS_LLM_API_KEY": "g"}) is True
    assert P.key_is_set(P.get_provider("ollama"), env={}) is False  # keyless provider


# --- memory + planner edges -------------------------------------------------


def test_agent_memory_recall_no_query(tmp_path):
    mem = PerAgentMemory(LongTermStore(tmp_path / "m.json")).for_role("r")
    mem.remember("one")
    mem.remember("two")
    assert [i["text"] for i in mem.recall()] == ["one", "two"]  # no filter branch


def test_plan_translate_fallback_to_view():
    avail = {"translate_view", "translate_text"}
    # "translate" with no following phrase -> empty phrase -> falls back to view.
    names = [c.name for c in plan_tool_calls("can you translate", avail)[0]]
    assert "translate_view" in names


async def test_mock_summarize_skips_empty_tool_content():
    res = await MockLLM().complete(
        [
            LLMMessage(role="user", content="x"),
            LLMMessage(role="tool", content="", tool_call_id="c", name="t"),  # empty -> skipped
            LLMMessage(role="tool", content='{"speech": "kept"}', tool_call_id="c2", name="t2"),
        ],
        [],
    )
    assert res.content == "kept"


# --- persona ----------------------------------------------------------------


def test_build_system_prompt_with_and_without_tools():
    assert "Tools available" not in build_system_prompt()
    assert "get_weather" in build_system_prompt(tool_names=["get_weather"])


# --- state ------------------------------------------------------------------


def test_state_untrack_multiple_refs():
    st = SessionState(session_id="S")
    obj = HoloObject(object_id="o1", widget_type="panel", transform=Transform(), props={"title": "T", "body": "B"})
    other = HoloObject(object_id="o2", widget_type="panel", transform=Transform(), props={"title": "T", "body": "B"})
    st.track(obj, "ref1")
    st.refs["ref1b"] = "o1"  # second ref to same object
    st.track(other, "ref2")
    st.untrack("o1")
    assert st.resolve("ref1") is None and st.resolve("ref1b") is None
    assert st.resolve("ref2") == "o2"  # untouched
    assert st.get_object("o1") is None


# --- trace ------------------------------------------------------------------


async def test_tracer_disabled_is_noop():
    sent = []

    async def emit(t, p=None, **k):
        sent.append((t, p))

    tr = Tracer(emit, enabled=False)
    assert tr.start("P", "g") is None
    tr.set_agents([{"agent_id": "a1", "role": "r"}])  # no current -> no-op
    tr.add_agent({"agent_id": "a2", "role": "r"})  # no current -> no-op
    await tr.event(agent_id="a1", role="r", kind="speech", label="x")
    assert sent == [] and tr.get() is None


async def test_tracer_get_variants():
    async def emit(t, p=None, **k):
        return None

    tr = Tracer(emit, enabled=True)
    assert tr.get() is None  # nothing yet
    tr.start("P1", "g1")
    tr._current = None  # simulate "between turns": fall back to ring
    assert tr.get().plan_id == "P1"
    assert tr.get("missing") is None


# --- perception tools: episodic-None + fallback transform -------------------


def _ctx_no_episodic(tmp_path, objects=None):
    s = SessionState(session_id="S")
    if objects is not None:
        s.perception.set_scene_objects({"objects": objects})
    return ToolContext(config=Config(data_dir=Path(tmp_path)), session=s,
                       catalog=WidgetCatalog.builtin(), longterm=LongTermStore(tmp_path / "m.json"),
                       episodic=None)


def test_perception_tools_without_episodic(tmp_path):
    # object without a position -> annotation transform fallback to head
    ctx = _ctx_no_episodic(tmp_path, objects=[{"label": "thing"}])
    r = PT._describe_view({}, ctx)
    assert any(a["anchor"] == "head" for a in r.data["observation"]["annotations"])
    assert PT._identify_object({}, ctx).data["object"] == "thing"
    assert PT._read_text({}, ctx).data["text"]
    assert PT._translate_view({}, ctx).data["translated"]
    assert PT._remember_object({"name": "x", "position": [1, 1, 1]}, ctx).directives
    assert PT._find_object({"name": "x"}, ctx).data["found"] is False  # no episodic recall
    ctx.session.perception.add_audio_event({"label": "bell"})
    assert "bell" in PT._identify_sound({}, ctx).data["speech"]
