---
name: market-briefing
description: >-
  Give a quick markets briefing — quotes for a watchlist and an optional trend
  chart. Use for "how are my stocks?", "price of AAPL", "market briefing", or a
  morning summary's finance section. Triggers: stocks, markets, ticker, quote,
  price of, my watchlist, how's the market, portfolio, finance briefing.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend. Offline returns deterministic mock quotes;
  live prices need a configured provider/key.
metadata:
  agent: research-agent
  category: research
  version: "1.0"
  author: jarvisvr
allowed-tools: get_stocks show_stocks show_chart
---
# Market Briefing

Fetch quotes for one or more symbols, speak a tight summary, and render a
`stocks_ticker` (plus an optional `chart_3d` for trend).

## Steps

1. **Resolve symbols.** From the request ("AAPL and Tesla") or the user's saved
   watchlist; default to a small index set if none given.
2. **Call `get_stocks{symbols}`.** Returns `data.quotes` ({symbol, price,
   change_pct, currency}) and a `stocks_ticker` directive.
3. **Summarize movers** in `agent.speech` (biggest up/down).
4. **Optional trend:** for "show the trend" build a `chart_3d` (line) from a
   series of closes.
5. **Helper:** to assemble ticker `props` from raw `SYMBOL:price[:change_pct]`
   pairs deterministically, use the bundled script:
   `python3 scripts/build_ticker.py AAPL:214.5:1.2 TSLA:178.3:-0.8`.

## Output

`stocks_ticker` (`show_stocks`, props per registry.json):

```json
{ "widget_type": "stocks_ticker",
  "transform": { "anchor": "head", "billboard": true },
  "props": { "title": "Watchlist",
             "symbols": [ { "symbol": "AAPL", "price": 214.5, "change_pct": 1.2, "currency": "USD" },
                          { "symbol": "TSLA", "price": 178.3, "change_pct": -0.8, "currency": "USD" } ],
             "scroll": true },
  "interactions": ["grab","tap","resize","drag"] }
```

Trend (`show_chart` → `chart_3d`):

```json
{ "widget_type": "chart_3d",
  "props": { "chart_type": "line", "title": "AAPL — 5d",
             "labels": ["Mon","Tue","Wed","Thu","Fri"],
             "series": [ { "name": "Close", "values": [210,212,209,213,214.5], "color": "#4FC3F7" } ],
             "y_axis_label": "USD" } }
```

`agent.speech`:

```json
{ "text": "Markets: AAPL is up 1.2% at $214.50, Tesla down 0.8% at $178.30.", "final": true }
```

## Bundled resources

- `scripts/build_ticker.py` — pure-stdlib helper that turns CLI `SYMBOL:price`
  pairs into validated `stocks_ticker` props JSON (mirrors the widget schema).

## Edge cases

- **Unknown symbol** → omit it and mention it wasn't found; don't guess a price.
- **Markets closed / stale** → label values as last close.
- **Crypto / FX** → same ticker schema; set `currency` appropriately.
- **Offline** → values are deterministic mocks; say so for "live price" asks.
- **Large watchlist (>6)** → ticker caps at a handful; suggest a `data_table`
  for the full list via `stage-agent present-data`.
