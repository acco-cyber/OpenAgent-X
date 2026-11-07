"""Run analytics — a deterministic numeric fingerprint of one journal.

Stats are a *view*, never a second source of truth: every counter that
``openagentx.trace.replay`` already derives is taken from replay itself so
the two views can never disagree. On top of that, stats add what replay
deliberately does not carry — per-type event counts, per-tool call/ok/fail
pairing, torn-tail/density flags, and the wall-clock span (reported
honestly, never used for grading or replay).

Determinism contract: the same file always yields the same dict and the
same rendered text.
"""

from __future__ import annotations

from .events import read_events_safe, sequence_dense
from .trace import replay


def run_stats(path) -> dict:
    """Compute the analytics fingerprint of one journal file."""
    events, torn = read_events_safe(path)
    st = replay(events)

    tools: dict = {}
    pending = None
    for ev in events:
        p = ev.payload or {}
        if ev.type == "tool_call":
            name = str(p.get("tool", ""))
            pending = name
            slot = tools.setdefault(name, {"calls": 0, "ok": 0, "failed": 0})
            slot["calls"] += 1
        elif ev.type == "tool_result" and pending is not None:
            tools[pending]["ok" if p.get("ok") else "failed"] += 1
            pending = None

    duration = round(events[-1].ts - events[0].ts, 6) if events else 0.0
    type_counts: dict = {}
    for ev in events:
        type_counts[ev.type] = type_counts.get(ev.type, 0) + 1

    return {
        "journal": str(path),
        "events": len(events),
        "torn_tail": torn,
        "dense": sequence_dense(events),
        "type_counts": {k: type_counts[k] for k in sorted(type_counts)},
        "runs_opened": st["runs_opened"],
        "runs_closed": st["runs_closed"],
        "steps": st["steps"],
        "thoughts": st["thoughts"],
        "tool_calls": st["tool_calls"],
        "tool_results": st["tool_results"],
        "tool_fails": st["tool_fails"],
        "tools": {k: tools[k] for k in sorted(tools)},
        "redactions": st["redactions"],
        "replies": st["replies"],
        "errors": st["errors"],
        "budgets": st["budgets"],
        "hooks": sum(1 for ev in events if ev.type == "hook"),
        "duration": duration,
    }


def render_stats(s: dict) -> str:
    """Deterministic human-readable rendering of the analytics fingerprint."""
    out: list = []
    out.append(f"stats {s['journal']}")
    out.append(f"events: {s['events']} (dense={s['dense']}, torn_tail={s['torn_tail']})")
    out.append(f"runs: opened={s['runs_opened']} closed={s['runs_closed']}")
    out.append(f"steps={s['steps']} thoughts={s['thoughts']} replies={s['replies']}")
    out.append(f"tool_calls={s['tool_calls']} results={s['tool_results']} "
               f"fails={s['tool_fails']} hooks={s['hooks']}")
    if s["tools"]:
        out.append("tools:")
        for name, t in s["tools"].items():
            out.append(f"  {name:<14} calls={t['calls']:<3} ok={t['ok']:<3} "
                       f"failed={t['failed']}")
    out.append(f"redactions={s['redactions']} errors={s['errors']} "
               f"budgets={s['budgets']}")
    out.append(f"duration: {s['duration']}s (wall-clock, reported not graded)")
    if s["type_counts"]:
        out.append("type counts: " + " ".join(
            f"{k}={v}" for k, v in s["type_counts"].items()))
    return "\n".join(out)
