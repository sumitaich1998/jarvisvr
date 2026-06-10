"""Built-in, network-free tools (plus an optional real-weather path).

Every tool returns structured ``data`` (including a ``speech`` suggestion the
mock LLM speaks back) and the holo directive(s) describing what to render.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from ...protocol import new_id, now_ms
from .base import (
    DestroyDirective,
    SpawnDirective,
    ToolContext,
    ToolRegistry,
    ToolResult,
    UpdateDirective,
)

log = logging.getLogger("jarvis.tools")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONDITION_PHRASE = {
    "clear": "clear skies",
    "clouds": "cloudy",
    "rain": "rainy",
    "snow": "snowy",
    "wind": "windy",
    "fog": "foggy",
    "storm": "stormy",
}

_CITY_PRESETS: dict[str, tuple[int, str, int, int]] = {
    # city -> (temp_c, condition, humidity_pct, wind_kph)
    "tokyo": (18, "clouds", 60, 12),
    "london": (12, "rain", 80, 18),
    "paris": (15, "clouds", 65, 14),
    "new york": (21, "clear", 50, 16),
    "san francisco": (17, "fog", 72, 22),
    "seattle": (13, "rain", 85, 10),
    "sydney": (24, "clear", 55, 20),
    "singapore": (30, "storm", 88, 8),
    "dubai": (38, "clear", 35, 12),
    "mumbai": (32, "clouds", 78, 15),
}


def _mock_weather(city: str) -> tuple[int, str, int, int]:
    key = city.strip().lower()
    if key in _CITY_PRESETS:
        return _CITY_PRESETS[key]
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
    conditions = list(_CONDITION_PHRASE.keys())
    temp = 5 + (h % 30)
    cond = conditions[(h // 7) % len(conditions)]
    humidity = 30 + (h // 11) % 60
    wind = 2 + (h // 13) % 30
    return temp, cond, humidity, wind


def _human_duration(seconds: int) -> str:
    seconds = int(seconds)
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    parts: list[str] = []
    if hrs:
        parts.append(f"{hrs} hour" + ("s" if hrs != 1 else ""))
    if mins:
        parts.append(f"{mins} minute" + ("s" if mins != 1 else ""))
    if secs and not hrs:
        parts.append(f"{secs} second" + ("s" if secs != 1 else ""))
    return " ".join(parts) or "0 seconds"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _get_weather(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    city = (args.get("city") or "San Francisco").strip() or "San Francisco"
    display = " ".join(w.capitalize() for w in city.split())
    source = "mock"

    temp_c, condition, humidity, wind = _mock_weather(city)
    if ctx.config and getattr(ctx.config, "weather_api_key", None):
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "q": city,
                        "units": "metric",
                        "appid": ctx.config.weather_api_key,
                    },
                )
                resp.raise_for_status()
                w = resp.json()
                temp_c = round(w["main"]["temp"])
                humidity = w["main"].get("humidity", humidity)
                wind = round(w.get("wind", {}).get("speed", 0) * 3.6)
                condition = (w.get("weather") or [{}])[0].get("main", condition).lower()
                display = w.get("name", display)
                source = "openweathermap"
        except Exception as exc:  # noqa: BLE001 - fall back to mock on any error
            log.warning("live weather lookup failed (%s); using mock data", exc)

    phrase = _CONDITION_PHRASE.get(condition, condition)
    props = {
        "city": display,
        "temp_c": temp_c,
        "condition": condition,
        "humidity_pct": int(humidity),
        "wind_kph": wind,
        "unit": "c",
    }
    return ToolResult(
        data={
            **props,
            "source": source,
            "speech": f"It's {temp_c}°C and {phrase} in {display}.",
        },
        directives=[
            SpawnDirective(
                widget_type="weather_orb",
                props=props,
                ref=f"weather:{city.lower()}",
                interactions=["grab", "tap"],
            )
        ],
    )


def _start_timer(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    duration = int(args.get("duration_seconds") or args.get("seconds") or 60)
    duration = max(1, duration)
    label = args.get("label") or "Timer"
    duration_ms = duration * 1000
    ends_at = now_ms() + duration_ms
    ref = f"timer:{new_id()[:8]}"
    ctx.session.store["last_timer_ref"] = ref
    timers = ctx.session.store.setdefault("timers", {})
    # `ends_at_ms` is tracked server-side only (not a catalog prop) so the agent
    # can recompute remaining time on pause/resume interactions.
    timers[ref] = {
        "label": label,
        "duration_ms": duration_ms,
        "remaining_ms": duration_ms,
        "state": "running",
        "ends_at_ms": ends_at,
    }

    props = {
        "label": label,
        "duration_ms": duration_ms,
        "remaining_ms": duration_ms,
        "state": "running",
        "mode": "countdown",
    }
    return ToolResult(
        data={
            "timer_ref": ref,
            "duration_s": duration,
            "speech": f"Timer started for {_human_duration(duration)}.",
        },
        directives=[
            SpawnDirective(
                widget_type="timer",
                props=props,
                ref=ref,
                interactions=["tap", "grab"],
            )
        ],
    )


def _stop_timer(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    ref = args.get("timer_ref") or ctx.session.store.get("last_timer_ref")
    timers = ctx.session.store.setdefault("timers", {})
    if not ref or ref not in timers:
        return ToolResult(
            data={"stopped": False, "speech": "There's no active timer to stop."}
        )
    timers.pop(ref, None)
    if ctx.session.store.get("last_timer_ref") == ref:
        ctx.session.store["last_timer_ref"] = None
    return ToolResult(
        data={"stopped": True, "speech": "Timer stopped."},
        directives=[DestroyDirective(ref=ref, fade_ms=200)],
    )


def _get_time(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    now = datetime.now().astimezone()
    time_str = now.strftime("%-I:%M %p") if hasattr(now, "strftime") else str(now)
    date_str = now.strftime("%A, %B %-d")
    tz = now.tzname() or ""
    return ToolResult(
        data={
            "time": time_str,
            "date": date_str,
            "tz": tz,
            "iso": now.isoformat(),
            "speech": f"It's {time_str}.",
        },
        directives=[
            SpawnDirective(
                widget_type="panel",
                props={"title": "Time", "body": f"{time_str}\n{date_str} {tz}".strip()},
                ref="time_panel",
                interactions=["grab", "tap"],
            )
        ],
    )


def _notes_panel_directive(notes: list[dict[str, Any]]) -> SpawnDirective:
    items = [n.get("text", "") for n in notes]
    return SpawnDirective(
        widget_type="panel",
        props={
            "title": "Notes",
            "body": "\n".join(f"• {t}" for t in items) or "No notes yet.",
        },
        ref="notes_panel",
        interactions=["grab", "tap", "resize"],
    )


def _take_note(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    text = (args.get("text") or "").strip()
    if not text:
        return ToolResult(data={"saved": False, "speech": "What would you like me to note?"})
    note = {"id": new_id(), "text": text, "ts": now_ms()}
    notes = ctx.longterm.append("notes", note)
    return ToolResult(
        data={"saved": True, "count": len(notes), "speech": "Noted."},
        directives=[_notes_panel_directive(notes)],
    )


def _list_notes(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    notes = ctx.longterm.get("notes", []) or []
    if not notes:
        speech = "You don't have any notes yet."
    elif len(notes) == 1:
        speech = "You have one note."
    else:
        speech = f"You have {len(notes)} notes."
    return ToolResult(
        data={"count": len(notes), "notes": [n.get("text") for n in notes], "speech": speech},
        directives=[_notes_panel_directive(notes)],
    )


def _set_reminder(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    text = (args.get("text") or "").strip()
    in_seconds = args.get("in_seconds")
    when = args.get("at")
    if not text:
        return ToolResult(data={"set": False, "speech": "What should I remind you about?"})
    reminder = {"id": new_id(), "text": text, "ts": now_ms(), "at": when, "in_seconds": in_seconds}
    reminders = ctx.longterm.append("reminders", reminder)
    when_phrase = ""
    if isinstance(in_seconds, (int, float)) and in_seconds > 0:
        when_phrase = f" in {_human_duration(int(in_seconds))}"
    elif when:
        when_phrase = f" at {when}"
    return ToolResult(
        data={
            "set": True,
            "count": len(reminders),
            "speech": f"I'll remind you to {text}{when_phrase}.",
        },
        directives=[
            SpawnDirective(
                widget_type="panel",
                props={
                    "title": "Reminder",
                    "body": f"{text}{when_phrase}".strip(),
                },
                ref=f"reminder:{reminder['id'][:8]}",
                interactions=["grab", "tap"],
            )
        ],
    )


def _show_panel(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    title = args.get("title") or "Panel"
    body = args.get("body") or args.get("text") or ""
    return ToolResult(
        data={"shown": True, "speech": args.get("speech") or f"Here's {title}."},
        directives=[
            SpawnDirective(
                widget_type="panel",
                props={"title": title, "body": body},
                ref="info_panel",
                interactions=["tap", "grab", "resize"],
            )
        ],
    )


def _show_text(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    text = args.get("text") or ""
    title = args.get("title") or "Jarvis"
    return ToolResult(
        # For free-form text we want Jarvis to also *speak* it.
        data={"shown": True, "speech": text or "Here you go."},
        directives=[
            SpawnDirective(
                widget_type="panel",
                props={"title": title, "body": text},
                ref="info_panel",
                interactions=["tap", "grab", "resize"],
            )
        ],
    )


def _open_widget(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    widget_type = (args.get("widget_type") or "").strip()
    props = args.get("props") or {}
    if not ctx.catalog.has(widget_type):
        known = ", ".join(ctx.catalog.names())
        return ToolResult(
            data={
                "opened": False,
                "speech": f"I don't have a '{widget_type}' widget. I can open: {known}.",
            },
            error="unknown_widget",
        )
    transform = None
    if args.get("anchor") or args.get("position"):
        transform = {}
        if args.get("anchor"):
            transform["anchor"] = args["anchor"]
        if args.get("position"):
            transform["position"] = args["position"]
    pretty = widget_type.replace("_", " ")
    return ToolResult(
        data={"opened": True, "widget_type": widget_type, "speech": f"Opening the {pretty}."},
        directives=[
            SpawnDirective(widget_type=widget_type, props=props, transform=transform)
        ],
    )


# ---------------------------------------------------------------------------
# Registry assembly
# ---------------------------------------------------------------------------


def _register_builtin_tools(reg: ToolRegistry) -> None:
    reg.add(
        "get_weather",
        "Get the current weather for a city and show a weather_orb hologram.",
        {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Tokyo'."}
            },
            "required": ["city"],
        },
        _get_weather,
    )

    reg.add(
        "start_timer",
        "Start a countdown timer and show a timer hologram.",
        {
            "type": "object",
            "properties": {
                "duration_seconds": {"type": "integer", "description": "Duration in seconds."},
                "label": {"type": "string", "description": "Optional timer label."},
            },
            "required": ["duration_seconds"],
        },
        _start_timer,
    )

    reg.add(
        "stop_timer",
        "Stop/cancel the most recent (or a specified) timer and remove its hologram.",
        {
            "type": "object",
            "properties": {
                "timer_ref": {"type": "string", "description": "Optional timer reference."}
            },
        },
        _stop_timer,
    )

    reg.add(
        "get_time",
        "Get the current local time and show it on a panel.",
        {"type": "object", "properties": {"timezone": {"type": "string"}}},
        _get_time,
    )

    reg.add(
        "take_note",
        "Save a note to long-term memory and show it on the notes panel.",
        {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "The note text."}},
            "required": ["text"],
        },
        _take_note,
    )

    reg.add(
        "list_notes",
        "List saved notes and show them on a panel.",
        {"type": "object", "properties": {}},
        _list_notes,
    )

    reg.add(
        "set_reminder",
        "Set a reminder and show a reminder card.",
        {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "What to be reminded about."},
                "in_seconds": {"type": "integer", "description": "Fire in N seconds."},
                "at": {"type": "string", "description": "Absolute time, e.g. '18:00'."},
            },
            "required": ["text"],
        },
        _set_reminder,
    )

    reg.add(
        "show_panel",
        "Show an information panel with a title and body.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["body"],
        },
        _show_panel,
    )

    reg.add(
        "show_text",
        "Show (and speak) a block of free-form text on a panel.",
        {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["text"],
        },
        _show_text,
    )

    reg.add(
        "open_widget",
        "Open any holographic widget from the catalog by type with optional props.",
        {
            "type": "object",
            "properties": {
                "widget_type": {"type": "string", "description": "Catalog widget id."},
                "props": {"type": "object", "description": "Widget-specific props."},
                "anchor": {
                    "type": "string",
                    "enum": ["world", "head", "hand_left", "hand_right", "surface"],
                },
                "position": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["widget_type"],
        },
        _open_widget,
    )


def build_default_registry(
    catalog: Any = None, tools_json_path: Any = None
) -> ToolRegistry:
    """Compose the full tool registry: built-ins + v1.1 perception + knowledge +
    dynamic widget-spawn tools (the latter derived from the widget catalog and,
    when present, ``holo-tools/tools.json``)."""
    from .knowledge_tools import register_knowledge_tools
    from .perception_tools import register_perception_tools
    from .widget_tools import register_widget_tools

    reg = ToolRegistry()
    _register_builtin_tools(reg)
    register_perception_tools(reg)
    register_knowledge_tools(reg)
    if catalog is not None:
        register_widget_tools(reg, catalog, tools_json_path)
    return reg


__all__ = ["build_default_registry"]
