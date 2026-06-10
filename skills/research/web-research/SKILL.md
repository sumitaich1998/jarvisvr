---
name: web-research
description: >-
  Look something up on the web and present a sourced answer, optionally opening
  the top result in a spatial browser. Use for factual questions, definitions,
  how-to lookups, comparisons, and "search for…/look up…/find information on…".
  Triggers: search, look up, find info, what is, who is, how do I, research,
  google, current weather/facts.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Offline/MockLLM returns deterministic results;
  set a real provider/key to fetch live data (see system-agent configure-llm).
metadata:
  agent: research-agent
  category: research
  version: "1.0"
  author: jarvisvr
allowed-tools: web_search show_web show_panel
---
# Web Research

Turn a question into a short, sourced spoken answer plus an optional artifact the
user can open and keep.

## Steps

1. **Form a tight query.** Extract entities and intent; drop filler. For "current
   X" questions (weather, scores, prices) prefer the dedicated specialist
   (`research-agent`'s `market-briefing`, or `web-research` for general facts).
2. **Call `web_search{query}`.** Returns `data.results` (title, snippet, url) and
   a `web_panel` directive for the top hit.
3. **Synthesize** a 1–2 sentence answer in `agent.speech`; cite the source name.
4. **Surface an artifact:** keep the `web_panel` for browsing, or summarize the
   findings onto a `panel` (`show_panel`) when reading beats browsing.
5. If the user wants depth on one result, hand to `summarize-source`.

## Output

`agent.speech`:

```json
{ "text": "Mixed reality blends real and virtual so they coexist and interact —
  here's the overview from Wikipedia.", "final": true }
```

`web_panel` (`show_web` / from `web_search`):

```json
{ "widget_type": "web_panel",
  "props": { "url": "https://en.wikipedia.org/wiki/Mixed_reality", "title": "Search: mixed reality",
             "interactive": true } }
```

Summary alternative (`show_panel` → `panel`):

```json
{ "widget_type": "panel",
  "props": { "title": "Mixed reality", "body": "Definition, history, and devices.",
             "sections": [ { "heading": "Top sources", "text": "Wikipedia, Nature, BBC" } ] } }
```

## Edge cases

- **No/low-quality results** → say what you tried and offer to refine the query;
  don't fabricate facts or URLs.
- **Time-sensitive** ("today", "latest") → note recency limits when offline; live
  fetch requires a configured provider.
- **Multi-source synthesis** (compare 3 articles) → delegate to `summarizer`
  sub-agents (one per source) and merge — see orchestration `agent-routing`.
- **News specifically** → use `news-digest`; **markets** → `market-briefing`.
- **Reading vs browsing** → long answers belong on a `panel`/`document_viewer`,
  not read aloud in full.
