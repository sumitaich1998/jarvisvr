---
name: web-research
description: >-
  Look up current information on the web (weather, facts, news, prices) and
  summarize it. Use for "search for…", "what's the weather", "look up…", or any
  knowledge question. May delegate per-source summarization to sub-agents.
license: MIT
metadata:
  agent: research-agent
  category: research
  version: "1.0"
allowed-tools: web_search get_weather get_news get_stocks
---

# Web research

1. Choose the right tool for the question (weather → get_weather, general → web_search).
2. For multi-source questions, delegate a `summarizer` sub-agent per source, then merge.
3. Present findings on a `panel`/`data_table` and give Jarvis a one-line digest.
