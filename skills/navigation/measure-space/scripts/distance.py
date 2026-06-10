#!/usr/bin/env python3
"""Compute spatial distance (and optional polyline length) between 3D points.

Mirrors the agent-backend perception `_measure` Euclidean math so the
navigation-agent can fill `measuring_tape` props consistently — useful offline,
in tests, or when planning a measurement before scene points are available.

Usage:
    python3 distance.py X,Y,Z X,Y,Z [X,Y,Z ...]
    python3 distance.py --unit cm 0,1,0 1,1,0
    python3 distance.py --json 0,1,0.5 0,1,1.2

Points are comma-separated meters. With >2 points the total polyline length is
returned. Prints a human line, or `--json` for ready-to-use widget props.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

_PER_METER = {"m": 1.0, "cm": 100.0, "ft": 3.28084, "in": 39.3701}


def parse_point(token: str) -> list[float]:
    parts = [p for p in token.split(",") if p != ""]
    if len(parts) != 3:
        raise ValueError(f"point '{token}' must be X,Y,Z (3 numbers in meters)")
    return [float(p) for p in parts]


def polyline_length_m(points: list[list[float]]) -> float:
    total = 0.0
    for a, b in zip(points, points[1:]):
        total += math.dist(a, b)
    return total


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Distance between 3D points (meters).")
    ap.add_argument("points", nargs="+", help="X,Y,Z points in meters")
    ap.add_argument("--unit", choices=sorted(_PER_METER), default="m")
    ap.add_argument("--json", action="store_true", help="emit measuring_tape props JSON")
    args = ap.parse_args(argv)

    try:
        points = [parse_point(t) for t in args.points]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if len(points) < 2:
        print("error: need at least two points", file=sys.stderr)
        return 2

    distance_m = round(polyline_length_m(points), 4)
    value = round(distance_m * _PER_METER[args.unit], 2)

    if args.json:
        props = {"points": points, "unit": args.unit,
                 "distance_m": distance_m, "mode": "distance"}
        print(json.dumps({"widget_type": "measuring_tape", "props": props}, indent=2))
    else:
        print(f"{value} {args.unit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
