"""Persisted user-authored agent roster (v1.3 §10.2).

User agents are created from the headset (``client.author_agent``) and stored in a
small JSON file so they survive restarts. They are merged with the built-in roster
at runtime and join routing immediately.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .agents import AgentSpec

log = logging.getLogger("jarvis.user_roster")


@dataclass
class UserAgent:
    role: str
    name: str
    persona: str = ""
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)

    def to_spec(self) -> AgentSpec:
        return AgentSpec(
            role=self.role,
            name=self.name or self.role.replace("-", " ").title(),
            persona=self.persona,
            tools=tuple(self.tools),
            skills=list(self.skills),
        )

    def to_json(self) -> dict:
        return {
            "role": self.role,
            "name": self.name,
            "persona": self.persona,
            "tools": list(self.tools),
            "skills": list(self.skills),
        }


def load_user_agents(path: Path) -> dict[str, UserAgent]:
    out: dict[str, UserAgent] = {}
    try:
        p = Path(path)
        if not p.is_file():
            return out
        data = json.loads(p.read_text(encoding="utf-8"))
        for entry in data if isinstance(data, list) else []:
            role = str(entry.get("role", "")).strip()
            if not role:
                continue
            out[role] = UserAgent(
                role=role,
                name=str(entry.get("name") or role),
                persona=str(entry.get("persona") or ""),
                tools=[str(t) for t in entry.get("tools", []) or []],
                skills=[str(s) for s in entry.get("skills", []) or []],
            )
    except Exception as exc:  # noqa: BLE001 - a corrupt file must not break boot
        log.warning("could not load user agents from %s (%s)", path, exc)
    return out


def save_user_agents(path: Path, agents: dict[str, UserAgent]) -> None:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(
            json.dumps([a.to_json() for a in agents.values()], indent=2), encoding="utf-8"
        )
        tmp.replace(p)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not persist user agents to %s (%s)", path, exc)


__all__ = ["UserAgent", "load_user_agents", "save_user_agents"]
