# Guide: Add an Agent Skill

JarvisVR agents are specialized with **Agent Skills** — small, directory-based packages in the
[agentskills.io](https://agentskills.io/specification) format. Adding a skill teaches an existing
agent a new sub-task; the backend discovers it automatically at startup. See
[`../ORCHESTRATION.md`](../ORCHESTRATION.md) for the big picture.

## 1. Create the skill directory

Skills live under `skills/<category>/<skill-name>/`. The directory name **must equal** the skill's
`name`.

```
skills/productivity/track-habit/
└── SKILL.md
```

> `name` rules: 1–64 chars, lowercase `a-z0-9` and single hyphens, no leading/trailing/consecutive
> hyphens, and it **must match the parent directory name**.

## 2. Write `SKILL.md`

YAML frontmatter, then a Markdown body:

```markdown
---
name: track-habit
description: >-
  Track a recurring daily habit and show streak progress. Use when the user wants to start,
  check, or update a habit/streak ("track my water intake", "did I meditate today?", "show my
  reading streak").
license: MIT
compatibility: Requires JarvisVR agent-backend.
metadata:
  agent: productivity-agent      # which specialist OWNS this skill (the routing key)
  category: productivity
  version: "1.0"
  author: your-name
allowed-tools: take_note list_notes show_panel
---

# Track a habit

## Steps
1. Resolve the habit name from the user's request.
2. Read prior entries with `list_notes` (namespace `habit:<name>`).
3. Append today's entry with `take_note`; compute the current streak.
4. Render the streak with `show_panel` (or `health_ring`), and confirm in one sentence.

## Examples
- "track my water intake" → note today's entry → `show_panel{title:"Water", body:"Day 4 🔥"}`.

## Edge cases
- Already logged today → don't double-count; report the existing streak.
- No prior entries → start the streak at day 1.
```

Key fields:

| Field | Required | Notes |
| ----- | -------- | ----- |
| `name` | ✅ | Matches the directory name (see rules above). |
| `description` | ✅ | ≤1024 chars. State **what it does and when to use it**, with trigger keywords — this is what routing matches against. |
| `metadata.agent` | ✅ (JarvisVR) | The owning agent **role id** (e.g. `perception-agent`, `research-agent`, `stage-agent`, or `jarvis` for orchestrator meta-skills). This is how the loader assigns the skill. |
| `metadata.category` | recommended | Mirrors the `skills/<category>/` folder. |
| `allowed-tools` | optional | Space-separated **real** JarvisVR tool ids (see [`HOLO_TOOLS.md`](../HOLO_TOOLS.md) / `holo-tools/tools.json` and the backend tools). |
| `license`, `compatibility`, `metadata.*` | optional | Per the spec. |

Keep the body under ~500 lines; move deep material into `references/`.

## 3. (Optional) Bundle resources

```
skills/productivity/track-habit/
├── SKILL.md
├── scripts/      # runnable helpers the skill may call
├── references/   # deeper docs loaded on demand
└── assets/       # templates / sample data
```

These load lazily (progressive disclosure) — only when the skill instructs the agent to read them.

## 4. How the backend picks it up

`jarvis_backend/skills/loader.py` scans `JARVIS_SKILLS_DIR` (default `<repo>/skills`) for
`**/SKILL.md`. At **discovery** it parses only `name`, `description`, and `metadata` (cheap), groups
skills by `metadata.agent`, and hands each agent its set. The full body is loaded only when the
agent **activates** the skill for a matching sub-task. A missing skill dir is fine — agents fall
back to their built-in tool mappings.

No registration step is required: drop the directory in, set `metadata.agent`, and restart the
backend.

## 5. Validate & test

```bash
# Frontmatter parses and name matches its directory:
python3 - <<'PY'
import glob, os, yaml
for f in glob.glob("skills/**/SKILL.md", recursive=True):
    fm = yaml.safe_load(open(f).read().split("---")[1])
    assert fm["name"] == os.path.basename(os.path.dirname(f)), f
    assert 1 <= len(fm["name"]) <= 64 and fm.get("description")
print("all skills valid")
PY

# Confirm the loader discovers it and assigns it to the right agent:
cd agent-backend && python -c "from pathlib import Path; from jarvis_backend.skills.loader import load_skills; r=load_skills(Path('../skills')); print(len(r), 'skills'); print('productivity-agent:', [s.name for s in r.for_agent('productivity-agent')])"
```

Then run the suite (`pytest agent-backend`) and try a relevant request against the backend — the
`productivity-agent` should now activate `track-habit` when routed a matching sub-task.

## See also
- [`../ORCHESTRATION.md`](../ORCHESTRATION.md) — the agent roster + skills system.
- [`add-a-widget.md`](./add-a-widget.md) and [`write-a-tool.md`](./write-a-tool.md) — if your skill needs a new hologram or tool.
- [Agent Skills specification](https://agentskills.io/specification).
