"""Thread identity, activity tracking and bounded idle eviction.

The registry is the single authority for "does this server still know this
chat". A request naming an unknown thread returns ``thread_not_found`` instead
of silently starting a new lesson (spec v3.0 sections 7.6 and 14.4).

Active threads are never evicted: a thread is active while a turn is running.
A thread paused at an interrupt is protected only for the idle window; once the
window elapses it is evicted like any other idle thread, and a client that
returns later gets ``thread_not_found`` and starts a fresh lesson.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field

# ULID-style: Crockford base32, 26 characters. Input is case-normalized.
THREAD_ID_PATTERN = re.compile(r"^thr_[0-9A-HJKMNP-TV-Z]{26}$")
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _random_suffix(length: int = 26) -> str:
    first = _CROCKFORD[int.from_bytes(os.urandom(1), "big") & 0b111]
    rest = "".join(_CROCKFORD[byte & 0b11111] for byte in os.urandom(length - 1))
    return first + rest


def new_thread_id() -> str:
    """Generate a valid client-side thread ID."""
    return "thr_" + _random_suffix()


def new_turn_id() -> str:
    """Generate a turn identifier for one request/response pair."""
    return "turn_" + _random_suffix()


def normalize_thread_id(value: str) -> str:
    """Canonical form: lowercase ``thr_`` prefix, uppercase Crockford suffix."""
    stripped = value.strip()
    if len(stripped) > 4 and stripped[:4].lower() == "thr_":
        return "thr_" + stripped[4:].upper()
    return stripped.upper()


def valid_thread_id(value: object) -> bool:
    return isinstance(value, str) and bool(THREAD_ID_PATTERN.match(normalize_thread_id(value)))


@dataclass
class ThreadRecord:
    thread_id: str
    created_at: float
    last_active_at: float
    turns: int = 0
    active: bool = False
    awaiting_user: bool = False


@dataclass
class ThreadRegistry:
    """Bounded registry of known chat threads with injectable clock."""

    max_threads: int = 200
    idle_seconds: float = 21_600.0
    clock: object = time.monotonic
    _records: dict[str, ThreadRecord] = field(default_factory=dict, repr=False)

    def _now(self) -> float:
        return float(self.clock())  # type: ignore[operator]

    def register(self, thread_id: str) -> ThreadRecord:
        """Return the record for a thread, creating it when the client starts a chat."""
        now = self._now()
        record = self._records.get(thread_id)
        if record is None:
            record = ThreadRecord(thread_id=thread_id, created_at=now, last_active_at=now)
            self._records[thread_id] = record
        return record

    def known(self, thread_id: str) -> bool:
        return thread_id in self._records

    def get(self, thread_id: str) -> ThreadRecord | None:
        return self._records.get(thread_id)

    def begin_turn(self, thread_id: str) -> ThreadRecord | None:
        """Mark a thread active. Returns None when a turn is already running."""
        record = self.register(thread_id)
        if record.active:
            return None
        record.active = True
        record.turns += 1
        record.last_active_at = self._now()
        return record

    def end_turn(self, thread_id: str, *, awaiting_user: bool) -> None:
        record = self._records.get(thread_id)
        if record is None:
            return
        record.active = False
        record.awaiting_user = awaiting_user
        record.last_active_at = self._now()

    def evict_idle(self) -> list[str]:
        """Evict idle threads, never an active one, and enforce the size bound."""
        now = self._now()
        evicted: list[str] = []
        for thread_id, record in list(self._records.items()):
            if record.active:
                continue
            if now - record.last_active_at > self.idle_seconds:
                del self._records[thread_id]
                evicted.append(thread_id)
        if len(self._records) > self.max_threads:
            idle = sorted(
                (record for record in self._records.values() if not record.active),
                key=lambda record: record.last_active_at,
            )
            for record in idle:
                if len(self._records) <= self.max_threads:
                    break
                del self._records[record.thread_id]
                evicted.append(record.thread_id)
        return evicted

    def stats(self) -> dict[str, int]:
        return {
            "known_threads": len(self._records),
            "active_threads": sum(1 for record in self._records.values() if record.active),
        }
