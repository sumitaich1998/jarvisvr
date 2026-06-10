"""Skill loader + registry with progressive disclosure (docs/ORCHESTRATION.md §5).

Scans a ``skills/`` directory for ``<category>/<name>/SKILL.md`` files, parses the
YAML frontmatter (``name``, ``description``, ``license``, ``compatibility``,
``metadata``, ``allowed-tools``) at *discovery* time, and loads the Markdown
*body* only when a skill is ``activate``-d. Skills are grouped by
``metadata.agent`` (the owning specialist role).

Robust by design: a missing/empty ``skills/`` dir yields an empty registry, and
agents still work via the backend's built-in tool mappings. YAML parsing uses
PyYAML when available, else a small dependency-free frontmatter parser (so the
base install stays light and offline).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

log = logging.getLogger("jarvis.skills")

_FRONTMATTER_RE = re.compile(r"^\ufeff?---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


@dataclass
class Skill:
    """A single Agent Skill. Body is lazily loaded (progressive disclosure)."""

    name: str
    description: str
    path: Path  # path to the SKILL.md file
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    _body: Optional[str] = None
    _activated: bool = False

    @property
    def agent(self) -> Optional[str]:
        """Owning specialist role id (JarvisVR convention: ``metadata.agent``)."""
        return self.metadata.get("agent")

    @property
    def category(self) -> Optional[str]:
        return self.metadata.get("category")

    @property
    def activated(self) -> bool:
        return self._activated

    @property
    def body(self) -> Optional[str]:
        return self._body

    def activate(self) -> str:
        """Load the full Markdown body on demand; returns it (cached)."""
        if not self._activated:
            try:
                _, body = _split_frontmatter(self.path.read_text(encoding="utf-8"))
                self._body = body.strip()
            except Exception as exc:  # noqa: BLE001
                log.warning("could not load body for skill %s (%s)", self.name, exc)
                self._body = ""
            self._activated = True
        return self._body or ""

    def card(self) -> dict[str, Any]:
        """The lightweight discovery card (no body) — what routing sees."""
        return {
            "name": self.name,
            "description": self.description,
            "agent": self.agent,
            "category": self.category,
            "allowed_tools": list(self.allowed_tools),
        }


class SkillRegistry:
    """In-memory skills, indexed by name and grouped by owning agent role."""

    def __init__(self, skills: Optional[list[Skill]] = None):
        self._skills: dict[str, Skill] = {}
        self._by_agent: dict[str, list[Skill]] = {}
        for s in skills or []:
            self.add(s)

    def add(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        if skill.agent:
            self._by_agent.setdefault(skill.agent, []).append(skill)

    def __len__(self) -> int:
        return len(self._skills)

    def names(self) -> list[str]:
        return sorted(self._skills)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def for_agent(self, role: str) -> list[Skill]:
        return list(self._by_agent.get(role, []))

    def agents(self) -> list[str]:
        return sorted(self._by_agent)

    def activate(self, skill: Union[str, Skill]) -> Optional[Skill]:
        """Load a skill's body (progressive disclosure). Accepts a name or Skill."""
        s = self.get(skill) if isinstance(skill, str) else skill
        if s is None:
            return None
        s.activate()
        return s

    def match(self, role: str, text: str) -> list[Skill]:
        """Skills for ``role`` ranked by relevance to ``text`` (keyword overlap).

        Falls back to all of the role's skills (so an agent always has something
        to activate when the registry is populated).
        """
        candidates = self.for_agent(role)
        if not candidates:
            return []
        low = (text or "").lower()
        scored: list[tuple[int, Skill]] = []
        for s in candidates:
            score = 0
            for token in set(re.split(r"[\s\-_]+", s.name.lower())) | _keywords(s.description):
                if len(token) >= 3 and token in low:
                    score += 1
            scored.append((score, s))
        scored.sort(key=lambda t: t[0], reverse=True)
        matched = [s for score, s in scored if score > 0]
        return matched or candidates

    def discovery_cards(self) -> list[dict[str, Any]]:
        return [s.card() for s in self._skills.values()]


# ---------------------------------------------------------------------------
# Loading + parsing
# ---------------------------------------------------------------------------


def load_skills(skills_dir: Optional[Path]) -> SkillRegistry:
    """Scan ``skills_dir`` for ``**/SKILL.md`` and build a :class:`SkillRegistry`."""
    registry = SkillRegistry()
    if not skills_dir:
        return registry
    skills_dir = Path(skills_dir)
    if not skills_dir.is_dir():
        log.info("skills dir %s not found; running with built-in tool mappings", skills_dir)
        return registry
    count = 0
    for skill_md in sorted(skills_dir.glob("**/SKILL.md")):
        try:
            skill = _parse_skill_file(skill_md)
            if skill is not None:
                registry.add(skill)
                count += 1
        except Exception as exc:  # noqa: BLE001 - one bad skill must not break discovery
            log.warning("skipping unparseable skill at %s (%s)", skill_md, exc)
    log.info(
        "loaded %d skill(s) from %s across %d agent(s)",
        count, skills_dir, len(registry.agents()),
    )
    return registry


def _parse_skill_file(path: Path) -> Optional[Skill]:
    front, _body = _split_frontmatter(path.read_text(encoding="utf-8"))
    meta = _parse_frontmatter(front)
    name = str(meta.get("name") or path.parent.name).strip()
    description = str(meta.get("description") or "").strip()
    if not name:
        return None
    raw_meta = meta.get("metadata") or {}
    metadata = {str(k): str(v) for k, v in raw_meta.items()} if isinstance(raw_meta, dict) else {}
    return Skill(
        name=name,
        description=description,
        path=path,
        license=_opt_str(meta.get("license")),
        compatibility=_opt_str(meta.get("compatibility")),
        metadata=metadata,
        allowed_tools=_as_tool_list(meta.get("allowed-tools")),
    )


def _split_frontmatter(text: str) -> tuple[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), m.group(2)


def _parse_frontmatter(block: str) -> dict[str, Any]:
    if not block.strip():
        return {}
    try:  # Prefer a real YAML parser when present.
        import yaml  # type: ignore

        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - fall back to the mini parser
        return _mini_yaml(block)


def _mini_yaml(block: str) -> dict[str, Any]:
    """A tiny YAML-frontmatter parser covering the SKILL.md subset.

    Supports: ``key: value``, folded/literal block scalars (``>``/``>-``/``|``),
    one level of nested mappings, and block/inline lists.
    """
    data: dict[str, Any] = {}
    lines = block.splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+):(.*)$", line)
        if not m:  # not a top-level key; skip
            i += 1
            continue
        key, rest = m.group(1).strip(), m.group(2).strip()
        if rest in (">", ">-", ">+", "|", "|-", "|+"):  # block scalar
            buf: list[str] = []
            i += 1
            while i < n and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                buf.append(lines[i].strip())
                i += 1
            joiner = "\n" if rest.startswith("|") else " "
            data[key] = joiner.join(buf).strip()
            continue
        if rest == "":  # nested mapping or block list
            child: dict[str, Any] = {}
            items: list[str] = []
            i += 1
            while i < n and lines[i].startswith((" ", "\t")):
                cl = lines[i].strip()
                if cl.startswith("- "):
                    items.append(_scalar(cl[2:].strip()))
                else:
                    cm = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", cl)
                    if cm:
                        child[cm.group(1).strip()] = _scalar(cm.group(2).strip())
                i += 1
            data[key] = items if items else child
            continue
        data[key] = _scalar(rest)  # inline scalar / list
        i += 1
    return data


def _scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [_scalar(p) for p in inner.split(",")] if inner else []
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    return value


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _as_tool_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    # space- or comma-separated string
    return [t for t in re.split(r"[\s,]+", str(value).strip()) if t]


def _keywords(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(w) >= 4}


__all__ = ["Skill", "SkillRegistry", "load_skills"]
