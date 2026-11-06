"""X-Trace: append-only JSONL run logs with replay and inspection.

A :class:`TraceLog` is the single write path for run events. One file per
run (``.openagentx/traces/<run_id>.jsonl`` by default) — plain JSONL keeps
traces ``grep``-able, ``git``-diffable and loadable with any tool, honoring
the "files over databases" rule.

Replay is a first-class operation: :meth:`TraceLog.replay` regenerates the
event stream so a run can be inspected, resumed, or re-rendered without the
original process.
"""

from __future__ import annotations

import os
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from openagentx.events import Actor, EventEnvelope

DEFAULT_TRACE_DIR = ".openagentx/traces"

OnEvent = Callable[[EventEnvelope], None]


@dataclass
class TraceLog:
    """Append-only event log for one run.

    Args:
        run_id: Stable identifier for the run; used as the file name.
        path: Target JSONL file. Defaults to ``.openagentx/traces/<run_id>.jsonl``.
        observers: Optional callables invoked with every appended event
            (used by the loop, UI bridges, or tests — never for policy).
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: Path | None = None
    observers: list[OnEvent] = field(default_factory=list)
    _sequence: int = -1

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = (
                Path(os.environ.get("OPENAGENTX_TRACE_DIR", DEFAULT_TRACE_DIR))
                / f"{self.run_id}.jsonl"
            )
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence = self._last_sequence()

    # ------------------------------------------------------------------ write

    def append(
        self,
        event_type: str,
        *,
        task_id: str | None = None,
        actor_type: str = "system",
        actor_id: str = "kernel",
        correlation_id: str | None = None,
        **payload: Any,
    ) -> EventEnvelope:
        """Persist one event and return it.

        The envelope is written **before** callers act on it: append first,
        effect after (event-before-effect rule).
        """
        envelope = EventEnvelope(
            event_type=event_type,
            task_id=task_id,
            sequence=self._sequence + 1,
            actor=Actor(type=actor_type, id=actor_id),
            payload=payload,
            correlation_id=correlation_id,
        )
        self._sequence = envelope.sequence
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(envelope.to_json() + "\n")
        for observer in self.observers:
            try:
                observer(envelope)
            except Exception:  # observers must never break the trace
                pass
        return envelope

    # ------------------------------------------------------------------- read

    def replay(self, path: Path | None = None) -> Iterator[EventEnvelope]:
        """Yield envelopes from a trace file in append order."""
        target = Path(path) if path else self.path
        if not target.exists():
            return
        with target.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield EventEnvelope.from_json(line)
                except Exception as exc:  # a torn tail line must not kill replay
                    yield EventEnvelope(
                        event_type="kernel.trace_corrupt_line",
                        task_id=None,
                        sequence=-1,
                        actor=Actor(type="system", id="trace"),
                        payload={"error": str(exc)},
                    )

    def find(self, event_type: str, path: Path | None = None) -> list[EventEnvelope]:
        """All envelopes of one type, in order."""
        return [e for e in self.replay(path) if e.event_type == event_type]

    def summary(self, path: Path | None = None) -> dict[str, Any]:
        """Compact run summary: counts per type plus wall-clock bounds."""
        events = list(self.replay(path))
        counts = Counter(e.event_type for e in events)
        times = [e.occurred_at for e in events if e.occurred_at]
        return {
            "run_id": self.run_id,
            "events": len(events),
            "by_type": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
            "started_at": min(times) if times else None,
            "ended_at": max(times) if times else None,
            "file": str(self.path),
        }

    # -------------------------------------------------------------- internals

    def _last_sequence(self) -> int:
        if not self.path.exists():
            return -1
        last = -1
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = max(last, int(EventEnvelope.from_json(line).sequence))
                except Exception:
                    continue
        return last


def newest_trace(trace_dir: str | os.PathLike[str] = DEFAULT_TRACE_DIR) -> Path | None:
    """Return the most recently modified trace file, if any."""
    directory = Path(trace_dir)
    if not directory.exists():
        return None
    files = [p for p in directory.glob("*.jsonl") if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)
