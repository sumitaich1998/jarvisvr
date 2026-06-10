#!/usr/bin/env python3
"""Build validated `stocks_ticker` widget props from CLI quote pairs.

Mirrors the holo-tools `stocks_ticker` props_schema so the research-agent can
assemble a ticker hologram deterministically (handy offline / in tests).

Usage:
    python3 build_ticker.py AAPL:214.5:1.2 TSLA:178.3:-0.8 NVDA:1200
    python3 build_ticker.py --title "My Watchlist" AAPL:214.5:1.2

Each quote is SYMBOL:price[:change_pct[:currency]] (currency defaults to USD).
Prints a JSON object: {"widget_type": "stocks_ticker", "props": {...}} that can
be dropped straight into a holo.spawn payload.
"""
from __future__ import annotations

import argparse
import json
import sys


def parse_quote(token: str) -> dict:
    parts = token.split(":")
    if len(parts) < 2:
        raise ValueError(f"quote '{token}' must be SYMBOL:price[:change_pct[:currency]]")
    symbol = parts[0].strip().upper()
    if not symbol:
        raise ValueError(f"quote '{token}' is missing a symbol")
    quote: dict = {"symbol": symbol, "price": float(parts[1])}
    if len(parts) >= 3 and parts[2] != "":
        quote["change_pct"] = round(float(parts[2]), 2)
    quote["currency"] = parts[3].strip().upper() if len(parts) >= 4 and parts[3] else "USD"
    return quote


def build_props(tokens: list[str], title: str = "Watchlist", scroll: bool = True) -> dict:
    symbols = [parse_quote(t) for t in tokens]
    if not symbols:
        raise ValueError("at least one quote is required")
    return {"title": title, "symbols": symbols, "scroll": scroll}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build stocks_ticker props from quotes.")
    ap.add_argument("quotes", nargs="+", help="SYMBOL:price[:change_pct[:currency]]")
    ap.add_argument("--title", default="Watchlist")
    ap.add_argument("--no-scroll", action="store_true")
    args = ap.parse_args(argv)
    try:
        props = build_props(args.quotes, title=args.title, scroll=not args.no_scroll)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"widget_type": "stocks_ticker", "props": props}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
