"""Agent Skills runtime (agentskills.io standard) — see docs/ORCHESTRATION.md §5.

Skills specialize agents. The loader implements *progressive disclosure*:
discovery parses only name+description+metadata (~100 tokens/skill); ``activate``
loads the full Markdown body on demand.
"""

from .loader import Skill, SkillRegistry, load_skills

__all__ = ["Skill", "SkillRegistry", "load_skills"]
