"""Agent Skills loader: parse, group-by-agent, progressive disclosure."""

from __future__ import annotations

from pathlib import Path

from jarvis_backend.skills import SkillRegistry, load_skills

FIX = Path(__file__).parent / "fixtures" / "skills"


def test_load_and_group_by_agent():
    reg = load_skills(FIX)
    assert len(reg) == 3
    assert set(reg.names()) == {"identify-object", "task-decomposition", "web-research"}
    assert reg.agents() == ["jarvis", "perception-agent", "research-agent"]
    assert {s.name for s in reg.for_agent("perception-agent")} == {"identify-object"}
    assert reg.for_agent("jarvis")[0].name == "task-decomposition"


def test_discovery_parses_metadata_without_body():
    reg = load_skills(FIX)
    s = reg.get("identify-object")
    assert s.description.startswith("Identify a real-world object")
    assert s.metadata["agent"] == "perception-agent"
    assert s.metadata["category"] == "perception"
    assert s.allowed_tools == ["identify_object", "look", "read_text"]
    # Progressive disclosure: the body is NOT loaded at discovery time.
    assert s.activated is False
    assert s.body is None
    card = s.card()
    assert card["agent"] == "perception-agent" and "name" in card and "body" not in card


def test_activate_loads_body_on_demand():
    reg = load_skills(FIX)
    s = reg.activate("identify-object")
    assert s.activated is True
    assert "vision_annotation" in (s.body or "")
    # idempotent + accessible via the skill object
    again = reg.get("identify-object").activate()
    assert "Identify object" in again


def test_allowed_tools_string_and_empty_list():
    reg = load_skills(FIX)
    assert reg.get("web-research").allowed_tools == [
        "web_search", "get_weather", "get_news", "get_stocks"
    ]
    assert reg.get("task-decomposition").allowed_tools == []


def test_match_ranks_by_keywords_with_fallback():
    reg = load_skills(FIX)
    m = reg.match("research-agent", "what's the weather in tokyo")
    assert m and m[0].name == "web-research"  # description mentions weather
    # role has a skill but no keyword overlap -> fall back to all role skills
    m2 = reg.match("perception-agent", "zzz unrelated")
    assert [s.name for s in m2] == ["identify-object"]
    # unknown role -> nothing
    assert reg.match("nope-agent", "anything") == []


def test_missing_dir_yields_empty_registry(tmp_path):
    reg = load_skills(tmp_path / "does-not-exist")
    assert isinstance(reg, SkillRegistry)
    assert len(reg) == 0
    assert reg.for_agent("perception-agent") == []
    assert reg.match("perception-agent", "x") == []


def test_none_dir_is_safe():
    reg = load_skills(None)
    assert len(reg) == 0
