"""Per-agent memory namespaces (v1.3 §10.1): isolation + persistence + inspect."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_backend.agent import Agent
from jarvis_backend.agent.agent_memory import PerAgentMemory
from jarvis_backend.agent.authoring import AuthoringError, agent_info
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.agent.memory import LongTermStore
from jarvis_backend.config import Config

FIX = Path(__file__).parent / "fixtures" / "skills"


def test_namespaces_are_isolated(tmp_path):
    store = LongTermStore(tmp_path / "m.json")
    pam = PerAgentMemory(store)
    research = pam.for_role("research-agent")
    productivity = pam.for_role("productivity-agent")

    research.remember("Tokyo is 18C and cloudy", kind="result")
    assert research.count() == 1
    assert research.recall("tokyo")  # finds its own item
    # The other agent cannot see it (separate namespace key).
    assert productivity.count() == 0
    assert productivity.recall("tokyo") == []


def test_long_term_persists_and_stays_isolated(tmp_path):
    path = tmp_path / "m.json"
    PerAgentMemory(LongTermStore(path)).for_role("research-agent").remember("persisted fact")
    reloaded = PerAgentMemory(LongTermStore(path))
    assert reloaded.for_role("research-agent").count() == 1
    assert reloaded.for_role("productivity-agent").count() == 0


def test_short_term_resets_each_turn(tmp_path):
    pam = PerAgentMemory(LongTermStore(tmp_path / "m.json"))
    mem = pam.for_role("research-agent")
    mem.note("turn scratch")
    assert mem.short_term()
    pam.begin_turn()
    assert mem.short_term() == []


def _agent(tmp_path, skills_dir=None) -> Agent:
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", skills_dir=skills_dir)
    return Agent.build(cfg, MockLLM())


def test_agent_inspect_builtin(tmp_path):
    a = _agent(tmp_path, FIX)
    info = agent_info(a, role="research-agent")
    assert info.role == "research-agent"
    assert info.source == "builtin"
    assert "get_weather" in info.tools
    assert any(s.name == "web-research" for s in info.skills)
    assert info.memory.items == 0

    a.per_agent_memory.for_role("research-agent").remember("looked up tokyo weather")
    info2 = agent_info(a, role="research-agent")
    assert info2.memory.items == 1
    assert info2.memory.recent[-1].text == "looked up tokyo weather"


def test_agent_inspect_unknown_role_errors(tmp_path):
    a = _agent(tmp_path)
    with pytest.raises(AuthoringError):
        agent_info(a, role="ghost-agent")
