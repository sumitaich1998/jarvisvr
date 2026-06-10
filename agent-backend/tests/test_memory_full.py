"""Conversation/long-term/episodic memory + per-agent memory edge cases."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend.agent.agent_memory import PerAgentMemory
from jarvis_backend.agent.llm import LLMMessage, ToolCall
from jarvis_backend.agent.memory import (
    ConversationMemory,
    EpisodicMemory,
    LongTermStore,
    _norm_object_name,
)


# --- ConversationMemory -----------------------------------------------------


def test_conversation_add_and_context():
    m = ConversationMemory()
    m.add_user("hi")
    m.add_assistant("hello", [ToolCall("c1", "t", {})])
    m.add_tool_result("c1", "t", '{"ok": 1}')
    msgs = m.messages()
    assert [x.role for x in msgs] == ["user", "assistant", "tool"]
    m.summary = "prior summary"
    ctx = m.as_context("SYS")
    assert ctx[0].role == "system" and ctx[0].content == "SYS"
    assert any("Conversation summary" in (x.content or "") for x in ctx)


def test_maybe_summarize_heuristic():
    m = ConversationMemory(max_messages=4)
    for i in range(10):
        m.add_user(f"msg {i}")
        m.add_assistant(f"reply {i}")
    m.add_tool_result("c", "tool_x", "{}")
    m.maybe_summarize()
    assert m.summary  # heuristic summary produced
    assert len(m.messages()) <= 4
    assert "User said" in m.summary or "Jarvis replied" in m.summary


def test_maybe_summarize_below_limit_noop():
    m = ConversationMemory(max_messages=24)
    m.add_user("only one")
    m.maybe_summarize()
    assert m.summary == ""


def test_maybe_summarize_custom_summarizer():
    m = ConversationMemory(max_messages=2)
    for i in range(6):
        m.add_user(str(i))
    m.maybe_summarize(summarizer=lambda old, prior: "CUSTOM")
    assert m.summary == "CUSTOM"


def test_maybe_summarize_failing_summarizer_falls_back():
    m = ConversationMemory(max_messages=2)
    for i in range(6):
        m.add_user(str(i))

    def boom(old, prior):
        raise RuntimeError("nope")

    m.maybe_summarize(summarizer=boom)
    assert m.summary  # fell back to heuristic


# --- LongTermStore ----------------------------------------------------------


def test_long_term_get_set_append_all(tmp_path):
    s = LongTermStore(tmp_path / "lt.json")
    assert s.get("k", "d") == "d"
    s.set("k", "v")
    assert s.get("k") == "v"
    assert s.append("list", 1) == [1]
    assert s.append("list", 2) == [1, 2]
    assert s.all()["k"] == "v"
    # reload from disk
    assert LongTermStore(tmp_path / "lt.json").get("k") == "v"


def test_long_term_append_replaces_non_list(tmp_path):
    s = LongTermStore(tmp_path / "lt.json")
    s.set("x", "scalar")
    assert s.append("x", 1) == [1]  # non-list value gets reset to a list


def test_long_term_load_corrupt(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json {")
    assert LongTermStore(p).all() == {}
    p.write_text("[1, 2, 3]")  # valid json but not a dict
    assert LongTermStore(p).all() == {}


def test_long_term_flush_error_is_swallowed(tmp_path):
    # Point the store at a *directory* so the atomic replace fails -> warning path.
    d = tmp_path / "adir"
    d.mkdir()
    s = LongTermStore(d)
    s.set("k", "v")  # must not raise
    assert s.get("k") == "v"  # in-memory still works


# --- EpisodicMemory ---------------------------------------------------------


def test_episodic_events_and_filter(tmp_path):
    em = EpisodicMemory(LongTermStore(tmp_path / "e.json"))
    em.record_event("vision", "saw a mug", anchor="world", extra_field="z")
    em.record_event("audio", "heard a bell")
    assert len(em.recent_events()) == 2
    assert em.recent_events(kind="audio")[0]["text"] == "heard a bell"
    assert em.recent_events(n=1)[0]["kind"] == "audio"


def test_episodic_spatial_recall_exact_and_fuzzy(tmp_path):
    em = EpisodicMemory(LongTermStore(tmp_path / "e.json"))
    em.remember_object("my keys", position=[1, 1, 1], anchor="world")
    assert em.recall_object("keys")["position"] == [1, 1, 1]  # normalized + fuzzy
    assert em.recall_object("the keys") is not None
    assert em.recall_object("spaceship") is None
    assert "keys" in em.seen_objects()


def test_episodic_facts(tmp_path):
    em = EpisodicMemory(LongTermStore(tmp_path / "e.json"))
    em.add_fact("Favorite Color", "blue")
    assert em.get_fact("favorite color") == "blue"
    assert em.get_fact("unknown") is None
    assert "favorite color" in em.all_facts()


def test_norm_object_name():
    assert _norm_object_name("my Keys!") == "keys"
    assert _norm_object_name("the Coffee Mug") == "coffee mug"


# --- per-agent memory edges -------------------------------------------------


def test_agent_memory_note_summary_reset(tmp_path):
    pam = PerAgentMemory(LongTermStore(tmp_path / "m.json"))
    mem = pam.for_role("research-agent")
    assert mem.summary().startswith("No memories")
    mem.note("scratch only")  # short-term only, not persisted
    assert mem.count() == 0 and mem.short_term()
    mem.remember("found tokyo weather", kind="result")
    assert "1 memory item" in mem.summary()
    assert mem.recall("tokyo") and mem.recall("nonexistent") == []
    assert mem.recent(1)[0]["text"] == "found tokyo weather"
    assert pam.roles() == ["research-agent"]
    pam.begin_turn()
    assert mem.short_term() == []
