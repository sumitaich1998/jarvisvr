"""Knowledge & integration tools: web search, news, stocks, calendar, navigation.

All return deterministic mock data so they work offline. Where an API key is
configured (``JARVIS_*`` env), a real implementation could be slotted in behind
the same interface; for now everything is a believable stub.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from .base import SpawnDirective, ToolContext, ToolRegistry, ToolResult


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def _mock_search_results(query: str) -> list[dict[str, str]]:
    h = _seed(query.lower())
    domains = ["wikipedia.org", "nature.com", "arxiv.org", "bbc.com", "github.com"]
    out = []
    for i in range(3):
        d = domains[(h >> (i * 3)) % len(domains)]
        out.append(
            {
                "title": f"{query.title()} — result {i + 1}",
                "snippet": f"An overview of {query} and why it matters, from {d}.",
                "url": f"https://{d}/search?q={query.replace(' ', '+')}",
            }
        )
    return out


def _mock_news(topic: str) -> list[dict[str, str]]:
    """Articles matching the news_feed schema: {id, headline, source, summary}."""
    base = topic.strip() or "world"
    h = _seed(base.lower())
    templates = [
        f"Breakthrough reported in {base}",
        f"Analysts weigh in on {base} trends",
        f"{base.title()}: what to watch this week",
        f"New study reshapes thinking on {base}",
        f"Markets react to {base} developments",
    ]
    rotated = templates[h % len(templates):] + templates[: h % len(templates)]
    return [
        {"id": f"a{i+1}", "headline": t, "source": "JarvisWire", "summary": f"{t}."}
        for i, t in enumerate(rotated[:4])
    ]


def _mock_quote(symbol: str) -> dict[str, Any]:
    """A stocks_ticker symbol entry: {symbol, price, change_pct, currency}."""
    h = _seed(symbol.upper())
    price = round(20 + (h % 600) + (h % 100) / 100.0, 2)
    change = round(((h >> 5) % 800) / 100.0 - 4.0, 2)  # -4.00 .. +4.00
    pct = round(change / price * 100, 2)
    return {"symbol": symbol.upper(), "price": price, "change_pct": pct, "currency": "USD"}


def _mock_calendar() -> list[dict[str, str]]:
    """Events matching the calendar schema: {id, title, start, end, location}."""
    base = datetime.now().replace(minute=0, second=0, microsecond=0)
    specs = [(2, "Standup", "Hangar 3"), (5, "Design review", "Lab"), (8, "1:1 with Pepper", "Office")]
    events = []
    for i, (offset, title, loc) in enumerate(specs):
        start = base + timedelta(hours=offset)
        events.append(
            {
                "id": f"e{i+1}",
                "title": title,
                "start": start.isoformat(),
                "end": (start + timedelta(hours=1)).isoformat(),
                "location": loc,
            }
        )
    return events


def _web_search(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    query = (args.get("query") or "").strip()
    if not query:
        return ToolResult(data={"speech": "What should I search for?"})
    results = _mock_search_results(query)
    speech = f"Here's what I found about {query}. Top result: {results[0]['title']}."
    return ToolResult(
        data={"speech": speech, "query": query, "results": results},
        directives=[
            SpawnDirective(
                widget_type="web_panel",
                props={"url": results[0]["url"], "title": f"Search: {query}"},
                ref="web_panel",
                interactions=["grab", "tap", "resize"],
            )
        ],
    )


def _get_news(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    topic = (args.get("topic") or "").strip()
    articles = _mock_news(topic)
    title = f"News — {topic}" if topic else "Top Headlines"
    speech = f"Here are the top headlines{(' about ' + topic) if topic else ''}. {articles[0]['headline']}."
    return ToolResult(
        data={"speech": speech, "articles": articles},
        directives=[
            SpawnDirective(
                widget_type="news_feed",
                props={"title": title, "category": topic or "general", "articles": articles},
                ref="news_feed",
                interactions=["grab", "tap", "resize"],
            )
        ],
    )


def _get_stocks(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    symbols = args.get("symbols") or ["AAPL", "TSLA", "NVDA"]
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.replace(",", " ").split() if s.strip()]
    quotes = [_mock_quote(s) for s in symbols[:6]] or [_mock_quote("AAPL")]
    summary = "; ".join(f"{q['symbol']} ${q['price']} ({q['change_pct']:+.1f}%)" for q in quotes)
    speech = f"Here are your stocks. {summary}."
    return ToolResult(
        data={"speech": speech, "quotes": quotes},
        directives=[
            SpawnDirective(
                widget_type="stocks_ticker",
                props={"title": "Markets", "symbols": quotes},
                ref="stocks",
                interactions=["grab", "tap"],
            )
        ],
    )


def _get_calendar(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    events = _mock_calendar()
    nxt = events[0]
    start_hhmm = nxt["start"][11:16]
    speech = f"You have {len(events)} events today. Next up: {nxt['title']} at {start_hhmm}."
    return ToolResult(
        data={"speech": speech, "events": events},
        directives=[
            SpawnDirective(
                widget_type="calendar",
                props={"title": "Today", "view": "agenda", "events": events},
                ref="calendar",
                interactions=["grab", "tap", "resize"],
            )
        ],
    )


# Word direction -> unit vector (Unity: +Z forward, +X right, +Y up).
_DIRECTION_VECTORS = {
    "straight ahead": [0.0, 0.0, 1.0],
    "left": [-1.0, 0.0, 0.0],
    "right": [1.0, 0.0, 0.0],
    "behind you": [0.0, 0.0, -1.0],
}


def _navigate_to(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    dest = (args.get("destination") or "").strip()
    if not dest:
        return ToolResult(data={"speech": "Where would you like to go?"})
    h = _seed(dest.lower())
    dist = 20 + h % 480
    word = ["left", "right", "straight ahead", "behind you"][h % 4]
    eta = round(dist / 80.0, 1)  # ~80 m/min walking
    speech = f"Head {word} for about {dist} meters to reach {dest}."
    return ToolResult(
        data={"speech": speech, "destination": dest, "distance_m": dist, "direction": word},
        directives=[
            SpawnDirective(
                widget_type="navigation_arrow",
                props={
                    "target_label": dest,
                    "direction": _DIRECTION_VECTORS[word],
                    "distance_m": float(dist),
                    "eta_min": eta,
                },
                ref="nav_arrow",
                interactions=["tap"],
            )
        ],
    )


def register_knowledge_tools(reg: ToolRegistry) -> None:
    reg.add(
        "web_search",
        "Search the web for information and show the results on a web panel.",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        _web_search,
    )
    reg.add(
        "get_news",
        "Get current news headlines (optionally about a topic).",
        {"type": "object", "properties": {"topic": {"type": "string"}}},
        _get_news,
    )
    reg.add(
        "get_stocks",
        "Get stock quotes for one or more ticker symbols.",
        {
            "type": "object",
            "properties": {"symbols": {"type": "array", "items": {"type": "string"}}},
        },
        _get_stocks,
    )
    reg.add(
        "get_calendar",
        "Show the user's calendar / agenda for today.",
        {"type": "object", "properties": {"date": {"type": "string"}}},
        _get_calendar,
    )
    reg.add(
        "navigate_to",
        "Give wayfinding directions to a destination and show a navigation arrow.",
        {"type": "object", "properties": {"destination": {"type": "string"}}, "required": ["destination"]},
        _navigate_to,
    )


__all__ = ["register_knowledge_tools"]
