"""In-headset authoring (v1.3 §10.2): round-trip + safety."""

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
from jarvis_backend.config import Config


def _agent(tmp_path) -> Agent:
    cfg = Config(
        holo_registry_path=None,
        data_dir=Path(tmp_path),
        llm_provider="mock",
        skills_dir=Path(tmp_path) / "skills",
    )
    return Agent.build(cfg, MockLLM())


# -- author_list -------------------------------------------------------------


def test_author_list_catalog(tmp_path):
    a = _agent(tmp_path)
    cat = build_server_authoring(a)
    roles = {ag.role for ag in cat.agents}
    assert {"research-agent", "stage-agent"} <= roles
    assert all(ag.source == "builtin" for ag in cat.agents)  # no user agents yet
    assert "get_weather" in cat.tools  # pickable tool ids
    assert "research" in cat.categories


# -- skill authoring round-trip ---------------------------------------------


def test_author_skill_create_reload_delete(tmp_path):
    a = _agent(tmp_path)
    cat = author_skill(a, {
        "op": "create",
        "name": "track-habit",
        "category": "productivity",
        "agent": "productivity-agent",
        "description": "Track a daily habit and show the streak.",
        "body": "# Track a habit\n1. Note it daily.",
        "allowed_tools": ["take_note", "show_panel"],
    })

    # 1) file appears under the skills root with metadata.source: user
    md = a.config.skills_dir / "productivity" / "track-habit" / "SKILL.md"
    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert "source: user" in text
    assert "agent: productivity-agent" in text

    # 2) registry hot-reloaded; owning agent gained it via the loader
    assert a.skills.get("track-habit") is not None
    assert any(s.name == "track-habit" for s in a.skills.for_agent("productivity-agent"))
    assert any(s.name == "track-habit" and s.source == "user" for s in cat.skills)

    # 3) agent_inspect surfaces the user skill
    info = agent_info(a, role="productivity-agent")
    assert any(s.name == "track-habit" and s.source == "user" for s in info.skills)

    # 4) update edits it in place
    author_skill(a, {"op": "update", "name": "track-habit", "category": "productivity",
                     "description": "Updated streak tracker."})
    assert a.skills.get("track-habit").description == "Updated streak tracker."

    # 5) delete removes it from disk + registry
    author_skill(a, {"op": "delete", "name": "track-habit"})
    assert a.skills.get("track-habit") is None
    assert not md.exists()


# -- skill safety ------------------------------------------------------------


def test_author_skill_rejects_path_traversal(tmp_path):
    a = _agent(tmp_path)
    with pytest.raises(AuthoringError) as e1:
        author_skill(a, {"op": "create", "name": "../evil", "category": "productivity", "description": "x"})
    assert e1.value.code == "invalid_skill"
    with pytest.raises(AuthoringError) as e2:
        author_skill(a, {"op": "create", "name": "ok", "category": "../../etc", "description": "x"})
    assert e2.value.code == "invalid_skill"
    # nothing escaped the skills root
    assert not (Path(tmp_path) / "etc").exists()


def test_author_skill_rejects_duplicates_and_reserved(tmp_path):
    a = _agent(tmp_path)
    author_skill(a, {"op": "create", "name": "dup", "category": "research",
                     "agent": "research-agent", "description": "first"})
    with pytest.raises(AuthoringError) as e:
        author_skill(a, {"op": "create", "name": "dup", "category": "research", "description": "again"})
    assert e.value.code == "name_conflict"
    with pytest.raises(AuthoringError) as e2:
        author_skill(a, {"op": "create", "name": "skills", "category": "research", "description": "reserved"})
    assert e2.value.code == "forbidden"


def test_cannot_modify_builtin_skill(tmp_path):
    a = _agent(tmp_path)
    # Simulate a *shipped* (built-in) skill: no metadata.source.
    d = a.config.skills_dir / "research" / "market-briefing"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        '---\nname: market-briefing\ndescription: "Builtin."\n'
        "metadata:\n  agent: research-agent\n  category: research\n---\n# Market briefing\n",
        encoding="utf-8",
    )
    a.reload_skills()
    assert a.skills.get("market-briefing") is not None
    with pytest.raises(AuthoringError) as e1:
        author_skill(a, {"op": "update", "name": "market-briefing", "category": "research", "description": "hax"})
    assert e1.value.code == "forbidden"
    with pytest.raises(AuthoringError) as e2:
        author_skill(a, {"op": "delete", "name": "market-briefing"})
    assert e2.value.code == "forbidden"


# -- agent authoring ---------------------------------------------------------


def test_author_agent_create_update_delete(tmp_path):
    a = _agent(tmp_path)
    cat = author_agent(a, {
        "op": "create", "role": "finance-agent", "name": "Finance",
        "persona": "A meticulous finance specialist.",
        "tools": ["get_stocks"], "skills": ["market-briefing"],
    })
    fin = next(ag for ag in cat.agents if ag.role == "finance-agent")
    assert fin.source == "user" and "get_stocks" in fin.tools

    # registered at runtime + persisted + joins the roster
    assert a.config.user_agents_file.is_file()
    assert a.get_spec("finance-agent") is not None
    assert "finance-agent" in a.agent_roles()
    info = agent_info(a, role="finance-agent")
    assert info.source == "user" and "meticulous" in info.persona

    author_agent(a, {"op": "update", "role": "finance-agent", "persona": "Sharp and fast."})
    assert a.get_spec("finance-agent").persona == "Sharp and fast."

    author_agent(a, {"op": "delete", "role": "finance-agent"})
    assert a.get_spec("finance-agent") is None
    assert "finance-agent" not in a.agent_roles()


def test_author_agent_safety(tmp_path):
    a = _agent(tmp_path)
    with pytest.raises(AuthoringError) as e1:
        author_agent(a, {"op": "create", "role": "Bad Role"})
    assert e1.value.code == "invalid_agent"
    with pytest.raises(AuthoringError) as e2:
        author_agent(a, {"op": "create", "role": "jarvis"})  # reserved
    assert e2.value.code == "forbidden"
    with pytest.raises(AuthoringError) as e3:
        author_agent(a, {"op": "create", "role": "research-agent"})  # builtin
    assert e3.value.code == "name_conflict"
    with pytest.raises(AuthoringError) as e4:
        author_agent(a, {"op": "update", "role": "research-agent"})  # builtin immutable
    assert e4.value.code == "forbidden"


def test_user_agent_joins_routing_without_stealing_builtins(tmp_path):
    a = _agent(tmp_path)
    from jarvis_backend.agent.agents import TOOL_TO_ROLE

    # A registry tool that no built-in specialist owns can be claimed by a user agent.
    unowned = [t for t in a.registry.names() if t not in TOOL_TO_ROLE]
    if unowned:
        tool = unowned[0]
        author_agent(a, {"op": "create", "role": "ops-agent", "name": "Ops", "tools": [tool]})
        assert a.role_for_tool(tool) == "ops-agent"
    # Built-in routes are never stolen.
    assert a.role_for_tool("get_weather") == "research-agent"
