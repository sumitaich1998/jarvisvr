"""Conversation memory (short-term) + a simple long-term key/value store.

* :class:`ConversationMemory` — bounded in-RAM transcript of the current session,
  exposed to the LLM as a message list, with a pluggable summarization hook that
  folds old turns into a running summary once the history grows too long.
* :class:`LongTermStore` — a tiny JSON-file key/value store shared across
  sessions (notes, reminders, preferences). Writes are atomic-ish (temp + rename).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from .llm import LLMMessage

log = logging.getLogger("jarvis.memory")


class ConversationMemory:
    """Short-term, per-session conversation history for the agent loop."""

    def __init__(self, *, max_messages: int = 24, summary: str = ""):
        # `max_messages` bounds the *running* tail kept verbatim; older turns are
        # summarized via the hook (if provided) or simply dropped.
        self.max_messages = max_messages
        self.summary = summary
        self._messages: list[LLMMessage] = []

    # -- mutation -----------------------------------------------------------

    def add(self, message: LLMMessage) -> None:
        self._messages.append(message)

    def add_user(self, text: str) -> None:
        self.add(LLMMessage(role="user", content=text))

    def add_assistant(
        self, content: Optional[str], tool_calls: Optional[list] = None
    ) -> None:
        self.add(LLMMessage(role="assistant", content=content, tool_calls=tool_calls))

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self.add(
            LLMMessage(
                role="tool", content=content, tool_call_id=tool_call_id, name=name
            )
        )

    # -- access -------------------------------------------------------------

    def messages(self) -> list[LLMMessage]:
        """The verbatim message tail (excludes the summary system note)."""
        return list(self._messages)

    def as_context(self, system_prompt: str) -> list[LLMMessage]:
        """Build the full prompt: system persona + running summary + tail."""
        out: list[LLMMessage] = [LLMMessage(role="system", content=system_prompt)]
        if self.summary:
            out.append(
                LLMMessage(
                    role="system",
                    content=f"Conversation summary so far:\n{self.summary}",
                )
            )
        out.extend(self._messages)
        return out

    # -- summarization hook -------------------------------------------------

    def maybe_summarize(
        self, summarizer: Optional[Callable[[list[LLMMessage], str], str]] = None
    ) -> None:
        """Fold the oldest turns into ``self.summary`` when over the limit.

        ``summarizer(old_messages, prior_summary) -> new_summary`` lets the agent
        plug in an LLM-backed summarizer. Without one, a terse heuristic summary
        is produced so memory stays bounded even in pure-mock/offline mode.
        """
        if len(self._messages) <= self.max_messages:
            return
        # Keep the most recent half; summarize the rest.
        keep_from = len(self._messages) - self.max_messages // 2
        old = self._messages[:keep_from]
        self._messages = self._messages[keep_from:]
        if summarizer is not None:
            try:
                self.summary = summarizer(old, self.summary)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("summarizer failed (%s); using heuristic summary", exc)
        self.summary = self._heuristic_summary(old, self.summary)

    @staticmethod
    def _heuristic_summary(old: list[LLMMessage], prior: str) -> str:
        lines = [prior] if prior else []
        for m in old:
            if m.role == "user" and m.content:
                lines.append(f"- User said: {m.content.strip()[:160]}")
            elif m.role == "assistant" and m.content:
                lines.append(f"- Jarvis replied: {m.content.strip()[:160]}")
            elif m.role == "tool" and m.name:
                lines.append(f"- Tool {m.name} ran.")
        # Bound the summary length itself.
        return "\n".join(lines[-40:])


class LongTermStore:
    """A minimal, thread-safe JSON key/value store persisted to a file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.is_file():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(self._data, dict):
                    self._data = {}
        except Exception as exc:  # noqa: BLE001
            log.warning("could not load long-term store %s (%s)", self.path, exc)
            self._data = {}

    def _flush(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, indent=2, default=str), "utf-8")
            tmp.replace(self.path)
        except Exception as exc:  # noqa: BLE001
            log.warning("could not persist long-term store %s (%s)", self.path, exc)

    # -- api ----------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._flush()

    def append(self, key: str, value: Any) -> list[Any]:
        """Append to a list value (creating it if needed); returns the list."""
        with self._lock:
            lst = self._data.get(key)
            if not isinstance(lst, list):
                lst = []
            lst.append(value)
            self._data[key] = lst
            self._flush()
            return list(lst)

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def _norm_object_name(name: str) -> str:
    n = (name or "").strip().lower()
    for prefix in ("my ", "the ", "a ", "an ", "some "):
        if n.startswith(prefix):
            n = n[len(prefix):]
    return n.strip(" .,!?")


class EpisodicMemory:
    """Episodic events, semantic facts, and a spatial index of seen objects.

    Backed by the long-term JSON store so recall (e.g. "where did I leave my
    keys?") survives restarts. All three live under dedicated top-level keys:
    ``episodes`` (timeline), ``facts`` (key/value semantics), and
    ``spatial_objects`` (name -> latest place) + ``spatial_history``.
    """

    def __init__(self, store: LongTermStore):
        self.store = store

    # -- episodic timeline --------------------------------------------------

    def record_event(
        self,
        kind: str,
        text: str,
        *,
        pose: Optional[dict] = None,
        anchor: Optional[str] = None,
        **extra: Any,
    ) -> dict[str, Any]:
        from uuid import uuid4

        event = {
            "id": str(uuid4()),
            "ts": _now_ms(),
            "kind": kind,
            "text": text,
            "pose": pose,
            "anchor": anchor,
            **extra,
        }
        self.store.append("episodes", event)
        return event

    def recent_events(self, n: int = 10, *, kind: Optional[str] = None) -> list[dict]:
        events = self.store.get("episodes", []) or []
        if kind:
            events = [e for e in events if e.get("kind") == kind]
        return events[-n:]

    # -- spatial index of seen objects -------------------------------------

    def remember_object(
        self,
        name: str,
        *,
        position: Optional[list] = None,
        anchor: str = "world",
        source: str = "user",
        frame_id: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> dict[str, Any]:
        key = _norm_object_name(name)
        record = {
            "name": name.strip(),
            "key": key,
            "position": position,
            "anchor": anchor,
            "ts": _now_ms(),
            "source": source,
            "frame_id": frame_id,
            "confidence": confidence,
        }
        index = self.store.get("spatial_objects", {}) or {}
        index[key] = record
        self.store.set("spatial_objects", index)
        self.store.append("spatial_history", record)
        return record

    def recall_object(self, name: str) -> Optional[dict[str, Any]]:
        key = _norm_object_name(name)
        index = self.store.get("spatial_objects", {}) or {}
        if key in index:
            return index[key]
        # Fuzzy: any stored key contained in / containing the query.
        for k, rec in index.items():
            if k and (k in key or key in k):
                return rec
        return None

    def seen_objects(self) -> dict[str, Any]:
        return self.store.get("spatial_objects", {}) or {}

    # -- semantic facts -----------------------------------------------------

    def add_fact(self, key: str, value: Any) -> None:
        facts = self.store.get("facts", {}) or {}
        facts[key.strip().lower()] = {"value": value, "ts": _now_ms()}
        self.store.set("facts", facts)

    def get_fact(self, key: str) -> Any:
        facts = self.store.get("facts", {}) or {}
        entry = facts.get(key.strip().lower())
        return entry.get("value") if isinstance(entry, dict) else None

    def all_facts(self) -> dict[str, Any]:
        return self.store.get("facts", {}) or {}


__all__ = ["ConversationMemory", "LongTermStore", "EpisodicMemory"]
