"""Journal throughput microbench — honest wall-clock, reported not graded.

The bench writes a synthetic, deterministic workload (fixed payload shapes
indexed by position, so the journal bytes depend only on the event count up
to wall-clock ``ts``) into a real ``Journal`` on a real filesystem, then
times three phases against the clock: append, read-back, and replay fold.

Honesty contract: timings are single-run wall-clock observations — noisy by
nature, never graded, never asserted by drills. What drills (and the CLI)
may rely on is the *structure*: the same event count always lands dense,
the read-back returns exactly what was written, and the report always
carries the same keys.
"""

from __future__ import annotations

import os
import tempfile
import time

from .events import Journal, read_events_safe, sequence_dense
from .trace import replay


def _payload(i: int) -> dict:
    """Deterministic workload: a realistic mix indexed by position."""
    kinds = [
        {"note": f"bench note {i} — deterministic workload line"},
        {"tool": "calc", "args": {"expr": f"{i % 97}*{i % 89}"}},
        {"tool": "write_file", "args": {"path": f"f{i % 16}.txt",
                                        "text": f"payload {i}"}},
        {"tool": "calc", "ok": True,
         "result": {"expr": f"{i % 97}*{i % 89}", "value": (i % 97) * (i % 89)}},
        {"text": f"thinking step {i}", "depth": i % 7},
    ]
    return kinds[i % len(kinds)]


def run_bench(events: int = 2000, workdir: str = "") -> dict:
    """Append ``events`` synthetic events, then read + replay them, timed."""
    events = int(events)
    wd = workdir or tempfile.mkdtemp(prefix="oax-bench-")
    os.makedirs(wd, exist_ok=True)
    jp = os.path.join(wd, "bench.jsonl")
    if os.path.exists(jp):
        os.remove(jp)
    open(jp, "a", encoding="utf-8").close()  # the journal exists even at 0 events

    j = Journal(jp)
    j.start_run("bench-1")
    t0 = time.perf_counter()
    for i in range(events):
        j.append("thought" if i % 5 == 4 else "tool_call", _payload(i))
    append_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    back, torn = read_events_safe(jp)
    read_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    replay(back)
    replay_s = time.perf_counter() - t0

    n = len(back)
    return {
        "journal": jp,
        "events": n,
        "planned_events": events,
        "dense": sequence_dense(back),
        "torn_tail": torn,
        "append_s": round(append_s, 6),
        "append_eps": round(events / append_s, 1) if append_s > 0 and events else 0.0,
        "read_s": round(read_s, 6),
        "read_eps": round(n / read_s, 1) if read_s > 0 and n else 0.0,
        "replay_s": round(replay_s, 6),
        "replay_eps": round(n / replay_s, 1) if replay_s > 0 and n else 0.0,
        "journal_bytes": os.path.getsize(jp),
    }


def render_bench(b: dict) -> str:
    """Deterministic *structure*; the timing values themselves are wall-clock."""
    out: list = []
    out.append(f"bench {b['journal']}")
    out.append(f"events: {b['events']} planned={b['planned_events']} "
               f"dense={b['dense']} torn_tail={b['torn_tail']} "
               f"bytes={b['journal_bytes']}")
    out.append(f"append: {b['append_s']}s  ({b['append_eps']} events/sec)")
    out.append(f"read:   {b['read_s']}s  ({b['read_eps']} events/sec)")
    out.append(f"replay: {b['replay_s']}s  ({b['replay_eps']} events/sec)")
    out.append("timings are single-run wall-clock — reported, never graded")
    return "\n".join(out)
