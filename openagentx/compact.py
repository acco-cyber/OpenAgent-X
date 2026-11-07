"""Journal compaction — a deterministic, lossy *secondary* representation.

The original journal is never touched (append-only invariant): compaction
reads events and writes a **new** journal holding a denser, renumbered stream.

- kept verbatim (renumbered): ``run_start`` / ``run_end`` / ``reply`` /
  ``handoff`` / ``error`` / ``budget`` / ``note`` / ``thought`` — and every
  other type not explicitly folded or dropped, so future event kinds survive
- folded: an adjacent ``tool_call``+``tool_result`` pair becomes one
  ``tool_fold`` event carrying ``{tool, ok, redactions}``; an orphan
  ``tool_call`` without its result stays verbatim (honest folding)
- dropped: ``step_start``/``step_end`` loop bookkeeping only

Compacted journals reload through ``load_trace``, replay deterministically,
and compact again to identical bytes. A torn source journal is refused —
compaction never launders an integrity failure.

Example:

    >>> evs = [Event(seq=0, run_id="r", ts=1.0, type="run_start", payload={"t": 1}),
    ...        Event(seq=1, run_id="r", ts=1.1, type="step_start", payload={"s": 0})]
    >>> [(e.seq, e.type) for e in compact_events(evs)]
    [(0, 'run_start')]
"""

from __future__ import annotations

import os

from .events import Event, read_events_safe

FOLD_TYPE = "tool_fold"
DROP_TYPES = frozenset({"step_start", "step_end", "step"})


def compact_events(events: list) -> list:
    """Fold, drop and renumber an event list (pure; no wall-clock input)."""
    out: list = []
    seq = 0
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.type in DROP_TYPES:
            i += 1
            continue
        if ev.type == "tool_call":
            nxt = events[i + 1] if i + 1 < len(events) else None
            if nxt is not None and nxt.type == "tool_result":
                rp = nxt.payload or {}
                payload = {
                    "tool": str((ev.payload or {}).get("tool", "")),
                    "ok": rp.get("ok"),
                    "redactions": int(rp.get("redactions", 0) or 0),
                }
                role = (ev.payload or {}).get("role")
                if role:
                    payload["role"] = role
                out.append(Event(seq=seq, run_id=ev.run_id, type=FOLD_TYPE,
                                 payload=payload, ts=ev.ts))
                seq += 1
                i += 2
                continue
        out.append(Event(seq=seq, run_id=ev.run_id, type=ev.type,
                         payload=dict(ev.payload or {}), ts=ev.ts))
        seq += 1
        i += 1
    return out


def compact_journal(src, dst) -> dict:
    """Write the compacted form of ``src`` to ``dst``; return honest stats.

    Raises on a torn-tail source: compaction is a clean-run tool, never a
    recovery shortcut that hides a broken write.
    """
    events, torn = read_events_safe(src)
    if torn:
        raise ValueError(f"refusing to compact {src}: torn tail (truncate first)")
    src_bytes = os.path.getsize(str(src))
    compacted = compact_events(events)
    lines = [e.to_json() for e in compacted]
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + ("\n" if lines else ""))
    dst_bytes = os.path.getsize(str(dst))
    folds = sum(1 for e in compacted if e.type == FOLD_TYPE)
    return {
        "src_events": len(events),
        "dst_events": len(compacted),
        "tool_folds": folds,
        "bytes_src": src_bytes,
        "bytes_dst": dst_bytes,
        "ratio": round(len(compacted) / len(events), 4) if events else 0.0,
    }
