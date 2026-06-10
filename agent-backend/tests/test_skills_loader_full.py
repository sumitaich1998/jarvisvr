"""Skill loader internals: mini-YAML fallback, scalars, frontmatter, edge cases."""

from __future__ import annotations

import sys
from pathlib import Path

from jarvis_backend.skills import loader as L
from jarvis_backend.skills.loader import Skill, SkillRegistry, load_skills

FIX = Path(__file__).parent / "fixtures" / "skills"


# --- _scalar / _as_tool_list / _opt_str / _keywords -------------------------


def test_scalar():
    assert L._scalar('"quoted"') == "quoted"
    assert L._scalar("'single'") == "single"
    assert L._scalar("[a, b, c]") == ["a", "b", "c"]
    assert L._scalar("[]") == []
    assert L._scalar("plain") == "plain"


def test_as_tool_list():
    assert L._as_tool_list(None) == []
    assert L._as_tool_list(["a", " b ", ""]) == ["a", "b"]
    assert L._as_tool_list("a b,c") == ["a", "b", "c"]


def test_opt_str_and_keywords():
    assert L._opt_str(None) is None
    assert L._opt_str("  ") is None
    assert L._opt_str(" x ") == "x"
    assert "weather" in L._keywords("Weather and Forecast!!")


# --- _mini_yaml -------------------------------------------------------------


def test_mini_yaml_block_scalars_maps_lists():
    block = (
        "name: my-skill\n"
        "description: >-\n"
        "  first line\n"
        "  second line\n"
        "body_literal: |\n"
        "  line one\n"
        "  line two\n"
        "metadata:\n"
        "  agent: research-agent\n"
        "  version: \"1.0\"\n"
        "allowed-tools:\n"
        "  - take_note\n"
        "  - show_panel\n"
        "# a comment\n"
        "inline_list: [a, b]\n"
    )
    data = L._mini_yaml(block)
    assert data["name"] == "my-skill"
    assert data["description"] == "first line second line"  # folded with spaces
    assert data["body_literal"] == "line one\nline two"  # literal keeps newlines
    assert data["metadata"] == {"agent": "research-agent", "version": "1.0"}
    assert data["allowed-tools"] == ["take_note", "show_panel"]
    assert data["inline_list"] == ["a", "b"]


def test_mini_yaml_skips_nonkey_and_blank():
    assert L._mini_yaml("\n  \nnot a key line\nkey: value\n") == {"key": "value"}


# --- _split_frontmatter / _parse_frontmatter --------------------------------


def test_split_frontmatter_none_and_bom():
    assert L._split_frontmatter("no frontmatter here") == ("", "no frontmatter here")
    front, body = L._split_frontmatter("\ufeff---\nname: x\n---\nBODY\n")
    assert "name: x" in front and body.strip() == "BODY"


def test_parse_frontmatter_yaml_path(monkeypatch):
    from types import SimpleNamespace

    # Inject a fake PyYAML so the yaml branch runs deterministically.
    monkeypatch.setitem(sys.modules, "yaml", SimpleNamespace(safe_load=lambda b: {"name": "z"}))
    assert L._parse_frontmatter("name: z")["name"] == "z"
    # safe_load returning a non-dict -> {}
    monkeypatch.setitem(sys.modules, "yaml", SimpleNamespace(safe_load=lambda b: [1, 2]))
    assert L._parse_frontmatter("- a\n- b") == {}


def test_parse_frontmatter_fallback(monkeypatch):
    block = 'name: s\ndescription: "d"\nmetadata:\n  agent: research-agent\n'
    # forced fallback: make `import yaml` fail -> mini parser
    monkeypatch.setitem(sys.modules, "yaml", None)
    data = L._parse_frontmatter(block)
    assert data["name"] == "s" and data["metadata"]["agent"] == "research-agent"
    assert L._parse_frontmatter("") == {}


def test_mini_yaml_nested_block_skips_junk_lines():
    block = "metadata:\n  agent: r\n  this line has no colon and no dash\n  version: \"1\"\n"
    data = L._mini_yaml(block)
    assert data["metadata"] == {"agent": "r", "version": "1"}


# --- Skill object -----------------------------------------------------------


def test_skill_activate_and_card(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text('---\nname: s\ndescription: "d"\nmetadata:\n  agent: x\n  category: c\n---\nthe body\n')
    s = Skill(name="s", description="d", path=p, metadata={"agent": "x", "category": "c"})
    assert s.activated is False and s.body is None
    assert s.activate() == "the body"
    assert s.activated is True and s.activate() == "the body"  # cached
    assert s.agent == "x" and s.category == "c"
    card = s.card()
    assert card["agent"] == "x" and "name" in card


def test_skill_activate_error_returns_empty(tmp_path):
    s = Skill(name="s", description="d", path=tmp_path / "missing.md")
    assert s.activate() == ""  # read failure swallowed
    assert s.activated is True


# --- SkillRegistry ----------------------------------------------------------


def test_registry_operations():
    reg = SkillRegistry()
    a = Skill(name="a", description="alpha thing", path=Path("a"), metadata={"agent": "r"})
    b = Skill(name="b", description="beta", path=Path("b"))  # no agent
    reg.add(a)
    reg.add(b)
    assert reg.names() == ["a", "b"]
    assert len(reg.all()) == 2
    assert reg.get("a") is a and reg.get("z") is None
    assert reg.for_agent("r") == [a]
    assert reg.agents() == ["r"]
    assert reg.activate("a") is a
    assert reg.activate(a) is a
    assert reg.activate("missing") is None
    assert reg.discovery_cards()[0]["name"] in {"a", "b"}


def test_registry_match_keywords_and_fallback():
    reg = SkillRegistry()
    reg.add(Skill(name="weather-skill", description="weather forecasts", path=Path("x"), metadata={"agent": "r"}))
    reg.add(Skill(name="other", description="misc", path=Path("y"), metadata={"agent": "r"}))
    matched = reg.match("r", "what is the weather")
    assert matched[0].name == "weather-skill"
    # no keyword overlap -> falls back to all of the role's skills
    assert len(reg.match("r", "zzzz")) == 2
    assert reg.match("nobody", "x") == []


# --- load_skills ------------------------------------------------------------


def test_load_skills_missing_and_none(tmp_path):
    assert len(load_skills(None)) == 0
    assert len(load_skills(tmp_path / "nope")) == 0


def test_load_skills_from_fixtures():
    reg = load_skills(FIX)
    assert len(reg) == 3
    assert "research-agent" in reg.agents()


def test_load_skills_skips_unparseable(tmp_path, monkeypatch):
    (tmp_path / "cat" / "good").mkdir(parents=True)
    (tmp_path / "cat" / "good" / "SKILL.md").write_text('---\nname: good\ndescription: "d"\n---\nbody\n')

    calls = {"n": 0}
    real = L._parse_skill_file

    def flaky(path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")  # exercise the except-skip path
        return real(path)

    monkeypatch.setattr(L, "_parse_skill_file", flaky)
    reg = load_skills(tmp_path)
    assert len(reg) == 0  # the single skill raised and was skipped


def test_parse_skill_file_returns_none_when_unnamed():
    from types import SimpleNamespace

    class _FakePath:
        # parent.name is empty so an empty frontmatter name resolves to "" -> None
        parent = SimpleNamespace(name="")

        def read_text(self, encoding="utf-8"):
            return "---\nname:\n---\nbody\n"

    assert L._parse_skill_file(_FakePath()) is None
