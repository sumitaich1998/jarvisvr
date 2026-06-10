---
name: summarize-source
description: >-
  Condense a single source — a URL, article, document, or pasted text — into key
  points the user can read at a glance. Use for "summarize this", "TL;DR",
  "give me the key points", or as a summarizer sub-agent merging one of several
  sources. Triggers: summarize, tldr, key points, gist, condense, brief me on
  this, what's the takeaway.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Works on provided text offline; URL fetch uses
  the configured provider where available.
metadata:
  agent: research-agent
  category: research
  version: "1.0"
  author: jarvisvr
allowed-tools: web_search show_panel show_document
---
# Summarize Source

Produce a faithful, compact summary of **one** source and present it as a
sectioned `panel` (or open the original in a `document_viewer`). This is also the
unit of work for a `summarizer` sub-agent in a fan-out (protocol §9.2 handoff).

## Steps

1. **Acquire the content.** Provided text → use directly. A URL → `web_search`
   (or fetch via provider) to obtain the page text.
2. **Extract structure:** a one-line thesis, 3–5 key points, and any numbers /
   dates / names worth keeping.
3. **Compose the summary.** Lead with the thesis; bullet the points; preserve
   source attribution. Stay faithful — never add claims the source doesn't make.
4. **Render** a `panel` with `sections`, or `show_document` to open the original
   alongside.
5. **Speak a 1-sentence TL;DR**; offer the full panel for detail.

## Output

`panel` (`show_panel`, props per registry.json):

```json
{ "widget_type": "panel",
  "props": { "title": "Summary — Quest 4 review",
             "body": "Strong display gains, same comfort tradeoffs.",
             "sections": [
               { "heading": "Key points", "text": "1) Brighter pancake lenses 2) Better passthrough 3) Heavier" },
               { "heading": "Source", "text": "TechNews, 2026" } ],
             "scrollable": true } }
```

Spoken TL;DR:

```json
{ "text": "TL;DR: a meaningful display upgrade, but comfort is unchanged.", "final": true }
```

## As a sub-agent (fan-out)

When merging several sources, each `summarizer` sub-agent (`a1.1`, `a1.2`, …)
summarizes one source and returns its `{thesis, points, source}`; the parent
`research-agent` reconciles overlaps and dedupes before handing to
`result-synthesis` / `present-data`.

## Edge cases

- **Paywalled / unreachable URL** → summarize the snippet you have and flag that
  it's partial; never invent the body.
- **Very long doc** → summarize hierarchically (per-section, then overall) and
  open it in `document_viewer` with `page_count` set.
- **Conflicting claims within the source** → present them as the source's open
  question, don't resolve silently.
- **Code/tabular content** → use `code_viewer` / `data_table` instead of prose.
