"""The specialist agent roster (docs/ORCHESTRATION.md §3).

Each specialist has a stable **role id**, a display name, a persona, and a
candidate **tool set** (existing backend/holo tools). Skills whose
``metadata.agent == role`` are auto-assigned from the :class:`SkillRegistry`.
``Jarvis`` (role ``orchestrator``, agent id ``jarvis``) is L0 and owns the
``orchestration/`` meta-skills; it never does domain work itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ORCHESTRATOR_ID = "jarvis"
ORCHESTRATOR_ROLE = "orchestrator"


@dataclass
class AgentSpec:
    role: str
    name: str
    persona: str
    tools: tuple[str, ...] = ()
    skills: list[str] = field(default_factory=list)  # filled from the skill registry


# Specialist roster (L1). Order is the canonical display order.
_ROSTER: list[AgentSpec] = [
    AgentSpec(
        "perception-agent", "Perception",
        "You see and understand the user's physical room via the passthrough "
        "camera, gaze, and detected objects.",
        ("identify_object", "describe_view", "read_text", "find_object",
         "remember_object", "identify_sound"),
    ),
    AgentSpec(
        "research-agent", "Research",
        "You answer knowledge questions using the web, news, weather, and markets, "
        "delegating per-source summarization to sub-agents when needed.",
        ("get_weather", "web_search", "get_news", "get_stocks"),
    ),
    AgentSpec(
        "productivity-agent", "Productivity",
        "You manage the user's time, reminders, notes, tasks, and calendar.",
        ("start_timer", "stop_timer", "get_time", "take_note", "list_notes",
         "set_reminder", "get_calendar"),
    ),
    AgentSpec(
        "smart-home-agent", "Smart Home",
        "You control the user's smart-home devices and scenes.",
        ("show_smart_home",),
    ),
    AgentSpec(
        "navigation-agent", "Navigation",
        "You handle maps, wayfinding, spatial memory, and measuring.",
        ("navigate_to", "measure"),
    ),
    AgentSpec(
        "media-agent", "Media",
        "You handle music, video, and generated imagery.",
        ("play_media", "show_media_player", "show_music_visualizer"),
    ),
    AgentSpec(
        "communication-agent", "Communication",
        "You handle translation, live captions, and drafting messages.",
        ("translate_text", "translate_view"),
    ),
    AgentSpec(
        "stage-agent", "Stage",
        "You are the spatial compositor: you decide how and where to render the "
        "team's results — arrangement, anchoring, and decluttering.",
        ("show_text", "show_panel", "open_widget"),
    ),
    AgentSpec(
        "system-agent", "System",
        "You manage settings, providers, privacy, and diagnostics.",
        ("show_settings",),
    ),
]

_BY_ROLE: dict[str, AgentSpec] = {a.role: a for a in _ROSTER}

ORCHESTRATOR_SPEC = AgentSpec(
    ORCHESTRATOR_ROLE, "Jarvis",
    "You are Jarvis, the orchestrator. You never do domain work yourself: you "
    "decompose the goal, route sub-tasks to specialists, run them, and synthesize "
    "one coherent reply.",
)

#: Tool id -> owning specialist role (the inverse of the roster tool sets).
TOOL_TO_ROLE: dict[str, str] = {
    tool: spec.role for spec in _ROSTER for tool in spec.tools
}

#: Nicer human labels for plan sub-tasks / agent_status, keyed by tool.
_TOOL_LABELS: dict[str, str] = {
    "get_weather": "get the weather",
    "start_timer": "start a timer",
    "stop_timer": "stop the timer",
    "get_time": "check the time",
    "take_note": "save a note",
    "list_notes": "list your notes",
    "set_reminder": "set a reminder",
    "get_calendar": "check your calendar",
    "identify_object": "identify what you're looking at",
    "describe_view": "describe the scene",
    "read_text": "read the text",
    "find_object": "find your object",
    "remember_object": "remember where it is",
    "identify_sound": "identify the sound",
    "web_search": "search the web",
    "get_news": "get the news",
    "get_stocks": "check the markets",
    "translate_text": "translate that",
    "translate_view": "read and translate",
    "navigate_to": "find the way",
    "measure": "measure the space",
}

_ROLE_LABELS: dict[str, str] = {
    "perception-agent": "look at your space",
    "research-agent": "look that up",
    "productivity-agent": "manage that for you",
    "smart-home-agent": "adjust your devices",
    "navigation-agent": "find the way",
    "media-agent": "play that",
    "communication-agent": "translate that",
    "stage-agent": "present the results",
    "system-agent": "update your settings",
}


def roster() -> list[AgentSpec]:
    return list(_ROSTER)


def roster_roles() -> list[str]:
    return [a.role for a in _ROSTER]


def get_spec(role: str) -> Optional[AgentSpec]:
    return _BY_ROLE.get(role)


def display_name(role: str) -> str:
    spec = _BY_ROLE.get(role)
    return spec.name if spec else role.replace("-", " ").title()


def role_for_tool(tool_name: str) -> str:
    """Map a tool id to the owning specialist role (with sensible fallbacks)."""
    if tool_name in TOOL_TO_ROLE:
        return TOOL_TO_ROLE[tool_name]
    # The exact tools below are already roster-owned (in TOOL_TO_ROLE), so these
    # two literal fallbacks are defensive belt-and-suspenders for future tools.
    if tool_name == "show_smart_home":  # pragma: no cover - redundant with TOOL_TO_ROLE
        return "smart-home-agent"
    if tool_name in ("play_media", "show_media_player", "show_music_visualizer"):  # pragma: no cover
        return "media-agent"
    if tool_name in ("show_settings", "show_system_launcher"):
        return "system-agent"
    if tool_name in ("show_navigation", "show_map"):
        return "navigation-agent"
    if tool_name.startswith("show_") or tool_name == "open_widget":
        return "stage-agent"
    return "stage-agent"


def label_for(role: str, tool_names: list[str]) -> str:
    """A short human sub-task label for the plan / agent_status."""
    for t in tool_names:
        if t in _TOOL_LABELS:
            return _TOOL_LABELS[t]
    return _ROLE_LABELS.get(role, "handle that")


def build_roster(registry, skill_registry) -> dict[str, AgentSpec]:
    """Return role -> AgentSpec with tools filtered to those present in the tool
    registry and skills auto-assigned from the skill registry by ``metadata.agent``."""
    out: dict[str, AgentSpec] = {}
    for base in _ROSTER:
        tools = tuple(t for t in base.tools if registry.has(t))
        skills = [s.name for s in skill_registry.for_agent(base.role)] if skill_registry else []
        out[base.role] = AgentSpec(base.role, base.name, base.persona, tools, skills)
    # Jarvis (orchestrator) gets the orchestration meta-skills.
    jarvis = AgentSpec(
        ORCHESTRATOR_ROLE, ORCHESTRATOR_SPEC.name, ORCHESTRATOR_SPEC.persona, (),
        [s.name for s in skill_registry.for_agent(ORCHESTRATOR_ID)] if skill_registry else [],
    )
    out[ORCHESTRATOR_ROLE] = jarvis
    return out


__all__ = [
    "AgentSpec",
    "ORCHESTRATOR_ID",
    "ORCHESTRATOR_ROLE",
    "ORCHESTRATOR_SPEC",
    "TOOL_TO_ROLE",
    "roster",
    "roster_roles",
    "get_spec",
    "display_name",
    "role_for_tool",
    "label_for",
    "build_roster",
]
