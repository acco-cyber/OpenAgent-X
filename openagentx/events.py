"""Append-only event journal (JSONL) — the single source of truth.

Every observable agent action becomes an :class:`Event` appended to a JSONL
journal. Invariants enforced here:

- **Dense sequence**: ``seq`` values are ``0..n-1`` with no gaps.
- **Append-only**: journals are opened for append; nothing is ever rewritten.
- **Torn-tail isolation**: an undecodable *trailing* line (crash mid-write) is
  reported as ``torn=True`` without corrupting the prefix; an undecodable
  *middle* line raises (integrity failure, never silently skipped).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Event:
    """One immutable, observable action in a run."""

    seq: int
    run_id: str
    type: str
    payload: dict
    ts: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)

    @staticmethod
    def from_json(line: str) -> "Event":
        d = json.loads(line)
        return Event(
            seq=int(d["seq"]),
            run_id=str(d["run_id"]),
            type=str(d["type"]),
            payload=dict(d.get("payload", {})),
            ts=float(d["ts"]),
        )


class Journal:
    """Append-only JSONL journal writer with resumable dense sequencing."""

    def __init__(self, path):
        self.path = str(path)
        self.run_id = ""
        self._seq = -1
        for ev in read_events(self.path):  # resume from disk if present
            self._seq = ev.seq

    @property
    def seq(self) -> int:
        return self._seq

    def start_run(self, run_id: str) -> None:
        self.run_id = run_id

    def _line(self, ev: Event) -> str:
        """Serialized form of one journal line (hook for enriched writers).

        The default is exactly the canonical event JSON; subclasses (e.g.
        :class:`openagentx.chain.ChainedJournal`) may append integrity
        metadata as extra top-level keys — ``Event.from_json`` ignores
        unknown keys, so plain readers stay compatible.
        """
        return ev.to_json()

    def append(self, type: str, payload: dict) -> Event:
        """Append one event; assigns the next dense seq. Returns the event."""
        if not self.run_id:
            raise RuntimeError("journal.start_run() must be called before append()")
        self._seq += 1
        ev = Event(
            seq=self._seq,
            run_id=self.run_id,
            type=type,
            payload=payload,
            ts=round(time.time(), 6),
        )
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(self._line(ev) + "\n")
            fh.flush()
        return ev

    def events(self) -> list:
        """Re-read all events from disk (append-only reads are stable)."""
        return read_events(self.path)


class TornMiddleError(RuntimeError):
    """An undecodable line exists *before* the last line: integrity failure."""


def read_events(path) -> list:
    """Strict read: any undecodable line raises TornMiddleError."""
    out: list = []
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return out
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            out.append(Event.from_json(line))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            raise TornMiddleError(f"journal {path}: undecodable line {i + 1}") from e
    return out


def read_events_safe(path):
    """Lenient read: returns ``(events, torn_tail)``.

    A trailing undecodable line isolates as ``torn_tail=True`` and the intact
    prefix is still returned. A torn line anywhere else raises TornMiddleError.
    """
    out: list = []
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return out, False
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            out.append(Event.from_json(line))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            if i == len(lines) - 1:
                return out, True  # torn tail isolated; prefix intact
            raise TornMiddleError(f"journal {path}: torn line at {i + 1} (not tail)")
    return out, False


def sequence_dense(events: list) -> bool:
    """True iff seq values are exactly 0..n-1."""
    return [ev.seq for ev in events] == list(range(len(events)))
