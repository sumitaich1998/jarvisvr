"""In-headset authoring runtime (v1.3 §10.2) + agent inspection (§10.1).

Lets users create/update/delete **Agent Skills** and **agents** at runtime, with
strict safety:

* **name/category/role** must match the agentskills.io name rules (lowercase
  ``[a-z0-9-]``, 1–64 chars) — this alone rejects path traversal and slashes;
* writes are **confined to the skills root** (defense-in-depth check);
* **built-ins are immutable** — only ``source: "user"`` items may be updated/deleted;
* authored skills carry ``metadata.source: user``; the :class:`SkillRegistry`
  **hot-reloads** so new capabilities are usable immediately.

Errors raise :class:`AuthoringError` with a PROTOCOL §10 code
(``invalid_skill`` | ``invalid_agent`` | ``name_conflict`` | ``forbidden`` |
``not_found``); the server maps these to ``server.error``.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Optional

from .. import protocol
from . import agents as roster_mod
from .user_roster import UserAgent

# agentskills.io name rule: 1–64 chars, lowercase alnum + hyphen, no leading/trailing hyphen.
_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")
_RESERVED_NAMES = {"skill", "skills", "con", "aux", "nul", "prn"}
_RESERVED_ROLES = {roster_mod.ORCHESTRATOR_ROLE, roster_mod.ORCHESTRATOR_ID, "summarizer"}

_STANDARD_CATEGORIES = [
    "perception", "research", "productivity", "smart-home", "navigation",
    "media", "communication", "stage", "system", "orchestration",
]


class AuthoringError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Catalog (author_list)
# ---------------------------------------------------------------------------


def build_server_authoring(agent) -> protocol.ServerAuthoring:
    reg = agent.registry
    skill_reg = agent.skills

    agents_out: list[protocol.AuthoringAgent] = []
    for spec in roster_mod.roster():
        agents_out.append(_authoring_agent(spec, "builtin", skill_reg))
    for ua in agent.user_agents.values():
        agents_out.append(_authoring_agent(ua.to_spec(), "user", skill_reg))

    skills_out = [
        protocol.AuthoringSkill(
            name=s.name,
            agent=s.agent,
            category=s.category,
            source=_skill_source(s),
            description=s.description,
        )
        for s in skill_reg.all()
    ]

    categories = sorted(set(_STANDARD_CATEGORIES) | {s.category for s in skill_reg.all() if s.category})
    return protocol.ServerAuthoring(
        agents=agents_out,
        skills=skills_out,
        categories=categories,
        tools=reg.names(),
    )


def _authoring_agent(spec, source: str, skill_reg) -> protocol.AuthoringAgent:
    return protocol.AuthoringAgent(
        role=spec.role,
        name=spec.name,
        source=source,
        skills=[s.name for s in skill_reg.for_agent(spec.role)],
        tools=list(spec.tools),
    )


# ---------------------------------------------------------------------------
# Skill authoring
# ---------------------------------------------------------------------------


def author_skill(agent, payload: dict[str, Any]) -> protocol.ServerAuthoring:
    op = payload.get("op")
    name = str(payload.get("name") or "").strip()
    if op not in ("create", "update", "delete"):
        raise AuthoringError(protocol.ErrorCode.INVALID_SKILL, "op must be create|update|delete")
    if not _NAME_RE.match(name):
        raise AuthoringError(protocol.ErrorCode.INVALID_SKILL, f"invalid skill name: {name!r}")
    if name in _RESERVED_NAMES:
        raise AuthoringError(protocol.ErrorCode.FORBIDDEN, f"reserved skill name: {name!r}")

    root = _skills_root(agent)
    existing = agent.skills.get(name)

    if op == "create":
        category = _valid_category(payload.get("category"))
        if existing is not None:
            raise AuthoringError(protocol.ErrorCode.NAME_CONFLICT, f"skill {name!r} already exists")
        skill_dir = _confined_dir(root, category, name)
        if skill_dir.exists():
            raise AuthoringError(protocol.ErrorCode.NAME_CONFLICT, f"skill {name!r} already exists on disk")
        if not str(payload.get("description") or "").strip():
            raise AuthoringError(protocol.ErrorCode.INVALID_SKILL, "description is required")
        _write_skill_md(skill_dir / "SKILL.md", name, category, payload)

    elif op == "update":
        if existing is None:
            raise AuthoringError(protocol.ErrorCode.NOT_FOUND, f"skill {name!r} not found")
        if _skill_source(existing) != "user":
            raise AuthoringError(protocol.ErrorCode.FORBIDDEN, "cannot edit a built-in skill")
        category = _valid_category(payload.get("category") or existing.category or "user")
        _ensure_within(root, existing.path)
        _write_skill_md(existing.path, name, category, payload, base=existing)

    else:  # delete
        if existing is None:
            raise AuthoringError(protocol.ErrorCode.NOT_FOUND, f"skill {name!r} not found")
        if _skill_source(existing) != "user":
            raise AuthoringError(protocol.ErrorCode.FORBIDDEN, "cannot delete a built-in skill")
        skill_dir = existing.path.parent
        _ensure_within(root, skill_dir)
        shutil.rmtree(skill_dir, ignore_errors=True)

    agent.reload_skills()
    return build_server_authoring(agent)


# ---------------------------------------------------------------------------
# Agent authoring
# ---------------------------------------------------------------------------


def author_agent(agent, payload: dict[str, Any]) -> protocol.ServerAuthoring:
    op = payload.get("op")
    role = str(payload.get("role") or "").strip()
    if op not in ("create", "update", "delete"):
        raise AuthoringError(protocol.ErrorCode.INVALID_AGENT, "op must be create|update|delete")
    if not _NAME_RE.match(role):
        raise AuthoringError(protocol.ErrorCode.INVALID_AGENT, f"invalid agent role: {role!r}")
    if role in _RESERVED_ROLES:
        raise AuthoringError(protocol.ErrorCode.FORBIDDEN, f"reserved role: {role!r}")

    builtin = agent.is_builtin_role(role)

    if op == "create":
        if builtin or role in agent.user_agents:
            raise AuthoringError(protocol.ErrorCode.NAME_CONFLICT, f"role {role!r} already exists")
        agent.register_user_agent(_user_agent_from(agent, payload, role))

    elif op == "update":
        if builtin:
            raise AuthoringError(protocol.ErrorCode.FORBIDDEN, "cannot edit a built-in agent")
        if role not in agent.user_agents:
            raise AuthoringError(protocol.ErrorCode.NOT_FOUND, f"role {role!r} not found")
        agent.register_user_agent(_user_agent_from(agent, payload, role, base=agent.user_agents[role]))

    else:  # delete
        if builtin:
            raise AuthoringError(protocol.ErrorCode.FORBIDDEN, "cannot delete a built-in agent")
        if role not in agent.user_agents:
            raise AuthoringError(protocol.ErrorCode.NOT_FOUND, f"role {role!r} not found")
        agent.remove_user_agent(role)

    return build_server_authoring(agent)


# ---------------------------------------------------------------------------
# Agent inspection (agent_inspect -> agent_info)
# ---------------------------------------------------------------------------


def agent_info(
    agent, *, role: Optional[str] = None, agent_id: Optional[str] = None, tracer=None
) -> protocol.ServerAgentInfo:
    if not role and agent_id and tracer is not None:
        role = _role_from_trace(tracer, agent_id)
    if not role:
        raise AuthoringError(protocol.ErrorCode.NOT_FOUND, "specify a role or a known agent_id")
    spec = agent.get_spec(role)
    if spec is None:
        raise AuthoringError(protocol.ErrorCode.NOT_FOUND, f"unknown role: {role!r}")
    source = "builtin" if agent.is_builtin_role(role) else "user"
    skills = [
        protocol.SkillInfo(name=s.name, description=s.description, source=_skill_source(s))
        for s in agent.skills.for_agent(role)
    ]
    mem = agent.per_agent_memory.for_role(role)
    recent = [
        protocol.MemoryRecentItem(ts=int(i.get("ts", 0)), text=str(i.get("text", ""))[:200])
        for i in mem.recent(5)
    ]
    return protocol.ServerAgentInfo(
        role=role,
        name=spec.name,
        source=source,
        persona=spec.persona,
        tools=list(spec.tools),
        skills=skills,
        memory=protocol.MemoryInfo(summary=mem.summary(), items=mem.count(), recent=recent),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skills_root(agent) -> Path:
    root = agent.config.skills_dir or (agent.config.data_dir / "skills")
    return Path(root)


def _valid_category(category: Optional[str]) -> str:
    cat = str(category or "").strip()
    if not cat:
        raise AuthoringError(protocol.ErrorCode.INVALID_SKILL, "category is required")
    if not _NAME_RE.match(cat):
        raise AuthoringError(protocol.ErrorCode.INVALID_SKILL, f"invalid category: {cat!r}")
    return cat


def _confined_dir(root: Path, category: str, name: str) -> Path:
    skill_dir = root / category / name
    _ensure_within(root, skill_dir)
    return skill_dir


def _ensure_within(root: Path, target: Path) -> None:
    root_r = Path(root).resolve()
    target_r = Path(target).resolve()
    if root_r != target_r and root_r not in target_r.parents:
        raise AuthoringError(protocol.ErrorCode.FORBIDDEN, "path escapes the skills root")


def _skill_source(skill) -> str:
    src = (skill.metadata or {}).get("source", "builtin")
    return "user" if str(src).lower() == "user" else "builtin"


def _one_line(text: str) -> str:
    return " ".join(str(text).split()).replace('"', "'")


def _write_skill_md(path: Path, name: str, category: str, payload: dict, base=None) -> None:
    owning = str(payload.get("agent") or "").strip()
    if not owning and base is not None:
        owning = base.agent or ""
    description = payload.get("description")
    if description is None and base is not None:
        description = base.description
    body = payload.get("body")
    if body is None and base is not None:
        base.activate()
        body = base.body
    allowed = payload.get("allowed_tools")
    if allowed is None and base is not None:
        allowed = base.allowed_tools

    lines = ["---", f"name: {name}", f'description: "{_one_line(description or name)}"']
    if payload.get("license"):
        lines.append(f"license: {_one_line(payload['license'])}")
    if payload.get("compatibility"):
        lines.append(f'compatibility: "{_one_line(payload["compatibility"])}"')
    lines.append("metadata:")
    if owning:
        lines.append(f"  agent: {owning}")
    lines.append(f"  category: {category}")
    lines.append("  source: user")
    lines.append('  version: "1.0"')
    if allowed:
        lines.append("allowed-tools: " + " ".join(str(t) for t in allowed))
    lines.append("---")
    md = "\n".join(lines) + "\n\n" + (str(body).strip() if body else f"# {name}") + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")


def _user_agent_from(agent, payload: dict, role: str, base: Optional[UserAgent] = None) -> UserAgent:
    name = payload.get("name")
    persona = payload.get("persona")
    tools = payload.get("tools")
    skills = payload.get("skills")
    return UserAgent(
        role=role,
        name=str(name if name is not None else (base.name if base else role)),
        persona=str(persona if persona is not None else (base.persona if base else "")),
        tools=_clean_tools(agent, tools if tools is not None else (base.tools if base else [])),
        skills=[str(s) for s in (skills if skills is not None else (base.skills if base else []))],
    )


def _clean_tools(agent, tools) -> list[str]:
    return [str(t) for t in (tools or []) if agent.registry.has(str(t))]


def _role_from_trace(tracer, agent_id: str) -> Optional[str]:
    trace = tracer.get()
    if trace is None:
        return None
    for a in trace.agents:
        if a.get("agent_id") == agent_id:
            return a.get("role")
    return None


__all__ = [
    "AuthoringError",
    "build_server_authoring",
    "author_skill",
    "author_agent",
    "agent_info",
]
