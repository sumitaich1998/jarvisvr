---
name: news-digest
description: >-
  Pull current headlines (optionally about a topic) and present a scrollable news
  feed with short summaries. Use for "what's the news?", "headlines about AI",
  "catch me up on…", or a morning briefing's news section. Triggers: news,
  headlines, what's happening, catch me up, latest on, current events, briefing.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Offline returns deterministic mock headlines;
  live feeds need a configured provider.
metadata:
  agent: research-agent
  category: research
  version: "1.0"
  author: jarvisvr
allowed-tools: get_news show_news
---
# News Digest

Give a quick, scannable read of the top stories and render them as a `news_feed`
the user can browse and tap into.

## Steps

1. **Determine scope.** Optional `topic` (e.g. "AI", "markets", "Tokyo"); none =
   top headlines.
2. **Call `get_news{topic?}`.** Returns `data.articles` (id, headline, source,
   summary) and a `news_feed` directive.
3. **Voice a 1–2 line digest** — the count and the lead headline — via
   `agent.speech`; render the feed for browsing.
4. **Drill-down:** a tapped article (`client.interaction{name:"open_article"}`)
   can be expanded with `summarize-source`.

## Output

`news_feed` (`show_news`, props per registry.json):

```json
{ "widget_type": "news_feed",
  "transform": { "anchor": "world", "billboard": true },
  "props": { "title": "News — AI", "category": "AI",
             "articles": [
               { "id": "a1", "headline": "New on-device model halves latency", "source": "JarvisWire",
                 "summary": "Inference moves to the headset." },
               { "id": "a2", "headline": "Analysts weigh in on AI trends", "source": "JarvisWire",
                 "summary": "What to watch this quarter." } ] },
  "interactions": ["grab","tap","resize","drag","dwell"] }
```

`agent.speech`:

```json
{ "text": "Top of the AI news: a new on-device model that halves latency, plus three more stories.",
  "final": true }
```

## Edge cases

- **Nothing for the topic** → say so and offer the general feed.
- **Sensitive/distressing headlines** → keep the tone neutral and factual.
- **Recency offline** → mention these are sample headlines unless a live provider
  is configured.
- **Deep dive on one story** → hand the article id to `summarize-source`.
- **Part of a briefing** → combine with `market-briefing` + `manage-calendar`
  under one `stage-agent present-data` layout.
