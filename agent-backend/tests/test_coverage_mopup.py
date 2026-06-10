"""Final mop-up: real-LLM decompose path, cancelled specialist, authoring +
agents fallbacks, and a couple of agent-loop guards."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from jarvis_backend import protocol
from jarvis_backend.agent import Agent
from jarvis_backend.agent import agents as A
from jarvis_backend.agent.authoring import (
    AuthoringError,
    _ensure_within,
    _role_from_trace,
    author_agent,
    author_skill,
)
from jarvis_backend.agent.llm import LLMProvider, LLMResult, MockLLM, ToolCall
from jarvis_backend.agent.trace import Tracer
from jarvis_backend.config import Config


class Recorder:
    def __init__(self):
        self.sent = []

    async def emit(self, type, payload=None, *, reply_to=None):
        self.sent.append(protocol.make(type, payload, session="S", reply_to=reply_to))

    def of(self, t):
        return [e for e in self.sent if e.type == t]


def _osession(tmp_path, **over):
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", **over)
    rec = Recorder()
    return Agent.build(cfg, MockLLM()).create_session("S", rec.emit), rec


def _agent(tmp_path) -> Agent:
    return Agent.build(Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", skills_dir=Path(tmp_path) / "skills"), MockLLM())


class _FakeLLM(LLMProvider):
    name = "openai"  # non-mock -> orchestrator uses the real decompose path

    def __init__(self, *, result=None, exc=None):
        self._result = result
        self._exc = exc

    async def complete(self, messages, tools, *, images=None):
        if self._exc is not None:
            raise self._exc
        return self._result


# --- orchestrator real-LLM decomposition ------------------------------------


async def test_decompose_real_llm_tool_calls(tmp_path):
    s, _ = _osession(tmp_path)
    s.agent.set_llm(_FakeLLM(result=LLMResult(tool_calls=[ToolCall("c", "get_weather", {"city": "Tokyo"})])))
    calls, direct = await s.orchestrator._decompose("anything")
    assert [c.name for c in calls] == ["get_weather"] and direct is None


async def test_decompose_real_llm_content_only(tmp_path):
    s, _ = _osession(tmp_path)
    s.agent.set_llm(_FakeLLM(result=LLMResult(content="hi there")))
    calls, direct = await s.orchestrator._decompose("anything")
    assert calls == [] and direct == "hi there"


async def test_decompose_real_llm_exception_falls_back(tmp_path):
    s, _ = _osession(tmp_path)
    s.agent.set_llm(_FakeLLM(exc=RuntimeError("boom")))
    calls, _ = await s.orchestrator._decompose("show weather in tokyo")
    assert [c.name for c in calls] == ["get_weather"]  # deterministic fallback


async def test_orchestrated_cancelled_specialist(tmp_path):
    s, rec = _osession(tmp_path)
    s._cancelled = True  # specialist tool loop breaks at the cancel check
    await s.handle_user_text("show weather in tokyo")
    assert rec.of("orchestration.plan")


# --- agent-loop guards ------------------------------------------------------


async def test_stream_speech_empty_noop(tmp_path):
    s, rec = _osession(tmp_path)
    await s._stream_speech("   ")
    assert rec.of("agent.speech") == []


async def test_barge_in_emit_thinking_error_swallowed(tmp_path):
    s, _ = _osession(tmp_path)
    started = asyncio.Event()

    async def turn():
        started.set()
        await asyncio.sleep(10)

    task = asyncio.create_task(s.run_turn(turn()))
    await started.wait()

    async def boom(*a, **k):
        raise RuntimeError("emit failed")

    s._emit_thinking = boom
    assert await s.barge_in("x") is True  # the except guard swallows the emit failure
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# --- agents fallbacks -------------------------------------------------------


def test_role_for_tool_system_launcher_and_navigation():
    assert A.role_for_tool("show_system_launcher") == "system-agent"
    assert A.role_for_tool("show_navigation") == "navigation-agent"


# --- authoring branches -----------------------------------------------------


def test_author_skill_create_requires_description(tmp_path):
    with pytest.raises(AuthoringError) as e:
        author_skill(_agent(tmp_path), {"op": "create", "name": "nodesc", "category": "research"})
    assert e.value.code == "invalid_skill"


def test_author_skill_create_requires_category(tmp_path):
    with pytest.raises(AuthoringError) as e:
        author_skill(_agent(tmp_path), {"op": "create", "name": "nocat", "description": "d"})
    assert e.value.code == "invalid_skill"


def test_author_skill_create_no_agent_with_license_compat(tmp_path):
    a = _agent(tmp_path)
    author_skill(a, {"op": "create", "name": "loose", "category": "research",
                     "description": "d", "license": "MIT", "compatibility": "needs perception"})
    md = (a.config.skills_dir / "research" / "loose" / "SKILL.md").read_text()
    assert "license: MIT" in md and "compatibility:" in md
    assert "  agent:" not in md  # no owning-agent line when agent omitted


def test_author_skill_update_reuses_description(tmp_path):
    a = _agent(tmp_path)
    author_skill(a, {"op": "create", "name": "u", "category": "research", "agent": "research-agent",
                     "description": "orig", "body": "# b"})
    author_skill(a, {"op": "update", "name": "u"})  # nothing provided -> reuse all
    assert a.skills.get("u").description == "orig"


def test_author_agent_delete_builtin_forbidden(tmp_path):
    with pytest.raises(AuthoringError) as e:
        author_agent(_agent(tmp_path), {"op": "delete", "role": "research-agent"})
    assert e.value.code == "forbidden"


def test_ensure_within_rejects_escape(tmp_path):
    with pytest.raises(AuthoringError) as e:
        _ensure_within(tmp_path / "root", tmp_path / "elsewhere" / "x")
    assert e.value.code == "forbidden"


def test_role_from_trace_branches():
    disabled = Tracer(emit=None, enabled=False)
    assert _role_from_trace(disabled, "a1") is None  # trace None
    tr = Tracer(emit=None, enabled=True)
    tr.start("P", "g")
    tr.set_agents([{"agent_id": "a1", "role": "research-agent"}])
    assert _role_from_trace(tr, "zzz") is None  # loop, no match
    assert _role_from_trace(tr, "a1") == "research-agent"
