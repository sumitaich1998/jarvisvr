"""Specialist roster: build_roster, tool->role routing, labels + user roster I/O."""

from __future__ import annotations

import json
from pathlib import Path

from jarvis_backend.agent import agents as A
from jarvis_backend.agent.tools import build_default_registry
from jarvis_backend.agent.user_roster import UserAgent, load_user_agents, save_user_agents
from jarvis_backend.catalog import WidgetCatalog
from jarvis_backend.skills.loader import load_skills

FIX = Path(__file__).parent / "fixtures" / "skills"


# --- agents.py --------------------------------------------------------------


def test_role_for_tool_mapping():
    assert A.role_for_tool("get_weather") == "research-agent"
    assert A.role_for_tool("start_timer") == "productivity-agent"
    assert A.role_for_tool("identify_object") == "perception-agent"
    assert A.role_for_tool("show_smart_home") == "smart-home-agent"
    assert A.role_for_tool("play_media") == "media-agent"
    assert A.role_for_tool("show_media_player") == "media-agent"
    assert A.role_for_tool("show_settings") == "system-agent"
    assert A.role_for_tool("show_map") == "navigation-agent"
    assert A.role_for_tool("show_text") == "stage-agent"
    assert A.role_for_tool("open_widget") == "stage-agent"
    assert A.role_for_tool("show_random_widget") == "stage-agent"  # show_ prefix fallback
    assert A.role_for_tool("mystery_tool") == "stage-agent"  # ultimate default


def test_label_for():
    assert A.label_for("research-agent", ["get_weather"]) == "get the weather"
    assert A.label_for("productivity-agent", ["start_timer"]) == "start a timer"
    # no tool label -> role label
    assert A.label_for("smart-home-agent", ["unknown_tool"]) == "adjust your devices"
    # unknown role -> generic default
    assert A.label_for("ghost-agent", ["unknown_tool"]) == "handle that"


def test_get_spec_and_display_name():
    assert A.get_spec("research-agent").name == "Research"
    assert A.get_spec("ghost") is None
    assert A.display_name("research-agent") == "Research"
    assert A.display_name("ghost-agent") == "Ghost Agent"  # title-cased fallback


def test_roster_and_roles():
    roles = A.roster_roles()
    assert "research-agent" in roles and "stage-agent" in roles
    assert len(A.roster()) == len(roles)


def test_build_roster_filters_tools_and_assigns_skills():
    catalog = WidgetCatalog.builtin()
    registry = build_default_registry(catalog=catalog)
    skills = load_skills(FIX)
    roster = A.build_roster(registry, skills)
    research = roster["research-agent"]
    assert all(registry.has(t) for t in research.tools)  # filtered to present tools
    assert "web-research" in research.skills  # fixture skill auto-assigned
    # the orchestrator role exists and owns the jarvis meta-skills
    assert A.ORCHESTRATOR_ROLE in roster
    jarvis = roster[A.ORCHESTRATOR_ROLE]
    assert "task-decomposition" in jarvis.skills


def test_build_roster_without_skill_registry():
    registry = build_default_registry(catalog=WidgetCatalog.builtin())
    roster = A.build_roster(registry, None)
    assert roster["research-agent"].skills == []


# --- user_roster ------------------------------------------------------------


def test_user_agent_to_spec_and_json():
    ua = UserAgent(role="finance-agent", name="Finance", persona="p", tools=["get_stocks"], skills=["s"])
    spec = ua.to_spec()
    assert spec.role == "finance-agent" and spec.tools == ("get_stocks",)
    j = ua.to_json()
    assert j["role"] == "finance-agent" and j["skills"] == ["s"]


def test_user_agent_to_spec_default_name():
    assert UserAgent(role="my-agent", name="").to_spec().name == "My Agent"


def test_load_user_agents_missing_and_valid(tmp_path):
    assert load_user_agents(tmp_path / "nope.json") == {}
    p = tmp_path / "ua.json"
    save_user_agents(p, {"finance-agent": UserAgent(role="finance-agent", name="Finance")})
    loaded = load_user_agents(p)
    assert "finance-agent" in loaded and loaded["finance-agent"].name == "Finance"


def test_load_user_agents_skips_entries_without_role(tmp_path):
    p = tmp_path / "ua.json"
    p.write_text(json.dumps([{"name": "no role"}, {"role": "ok-agent", "name": "OK"}]))
    loaded = load_user_agents(p)
    assert list(loaded) == ["ok-agent"]


def test_load_user_agents_corrupt_file(tmp_path):
    p = tmp_path / "ua.json"
    p.write_text("{not json")
    assert load_user_agents(p) == {}


def test_save_user_agents_error_is_swallowed(tmp_path):
    # Saving to a path whose parent is a file -> write fails, but no exception.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    save_user_agents(blocker / "sub" / "ua.json", {"a": UserAgent(role="a", name="A")})
