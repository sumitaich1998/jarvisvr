"""Authoring runtime: remaining error/validation branches + agent_info resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_backend.agent import Agent
from jarvis_backend.agent.authoring import (
    AuthoringError,
    agent_info,
    author_agent,
    author_skill,
    build_server_authoring,
)
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.agent.trace import Tracer
from jarvis_backend.config import Config


def _agent(tmp_path) -> Agent:
    cfg = Config(holo_registry_path=None, data_dir=Path(tmp_path), llm_provider="mock", skills_dir=Path(tmp_path) / "skills")
    return Agent.build(cfg, MockLLM())


# --- skill authoring branches ----------------------------------------------


def test_author_skill_invalid_op(tmp_path):
    with pytest.raises(AuthoringError) as e:
        author_skill(_agent(tmp_path), {"op": "frobnicate", "name": "x"})
    assert e.value.code == "invalid_skill"


def test_author_skill_update_and_delete_not_found(tmp_path):
    a = _agent(tmp_path)
    with pytest.raises(AuthoringError) as e1:
        author_skill(a, {"op": "update", "name": "ghost", "category": "research", "description": "d"})
    assert e1.value.code == "not_found"
    with pytest.raises(AuthoringError) as e2:
        author_skill(a, {"op": "delete", "name": "ghost"})
    assert e2.value.code == "not_found"


def test_author_skill_create_invalid_category(tmp_path):
    with pytest.raises(AuthoringError) as e:
        author_skill(_agent(tmp_path), {"op": "create", "name": "ok", "category": "Bad Category", "description": "d"})
    assert e.value.code == "invalid_skill"


def test_author_skill_create_conflicts_with_disk(tmp_path):
    a = _agent(tmp_path)
    # Pre-create the dir on disk WITHOUT reloading the registry.
    d = a.config.skills_dir / "research" / "ondisk"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: ondisk\ndescription: \"x\"\n---\n# x\n")
    with pytest.raises(AuthoringError) as e:
        author_skill(a, {"op": "create", "name": "ondisk", "category": "research", "description": "d"})
    assert e.value.code == "name_conflict"


def test_author_skill_update_reuses_body(tmp_path):
    a = _agent(tmp_path)
    author_skill(a, {"op": "create", "name": "keep", "category": "research", "agent": "research-agent",
                     "description": "orig", "body": "# original body", "allowed_tools": ["web_search"]})
    # update with only a new description -> body + agent + tools reused from the base
    author_skill(a, {"op": "update", "name": "keep", "description": "new desc"})
    s = a.skills.get("keep")
    assert s.description == "new desc"
    assert "original body" in s.activate()
    assert s.allowed_tools == ["web_search"]


# --- agent authoring branches ----------------------------------------------


def test_author_agent_invalid_op_and_role(tmp_path):
    a = _agent(tmp_path)
    with pytest.raises(AuthoringError) as e1:
        author_agent(a, {"op": "nope", "role": "x-agent"})
    assert e1.value.code == "invalid_agent"
    with pytest.raises(AuthoringError) as e2:
        author_agent(a, {"op": "create", "role": "BAD ROLE"})
    assert e2.value.code == "invalid_agent"


def test_author_agent_update_delete_not_found(tmp_path):
    a = _agent(tmp_path)
    with pytest.raises(AuthoringError) as e1:
        author_agent(a, {"op": "update", "role": "ghost-agent", "name": "G"})
    assert e1.value.code == "not_found"
    with pytest.raises(AuthoringError) as e2:
        author_agent(a, {"op": "delete", "role": "ghost-agent"})
    assert e2.value.code == "not_found"


def test_build_server_authoring_includes_user_agent(tmp_path):
    a = _agent(tmp_path)
    author_agent(a, {"op": "create", "role": "finance-agent", "name": "Finance", "tools": ["get_stocks"]})
    cat = build_server_authoring(a)
    fin = next(ag for ag in cat.agents if ag.role == "finance-agent")
    assert fin.source == "user"


# --- agent_info resolution --------------------------------------------------


def test_agent_info_by_agent_id_via_tracer(tmp_path):
    a = _agent(tmp_path)
    tracer = Tracer(emit=None, enabled=True)
    tracer.start("P1", "goal")
    tracer.set_agents([{"agent_id": "a1", "role": "research-agent", "parent": "jarvis", "level": 1}])
    info = agent_info(a, agent_id="a1", tracer=tracer)
    assert info.role == "research-agent"


def test_agent_info_unresolvable(tmp_path):
    a = _agent(tmp_path)
    tracer = Tracer(emit=None, enabled=True)
    tracer.start("P1", "goal")
    with pytest.raises(AuthoringError) as e1:
        agent_info(a, agent_id="zzz", tracer=tracer)  # not in trace
    assert e1.value.code == "not_found"
    with pytest.raises(AuthoringError) as e2:
        agent_info(a)  # neither role nor agent_id
    assert e2.value.code == "not_found"
