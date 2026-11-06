"""Trace layer: safe loads, deterministic replay, and canonical views.

`replay` recomputes derived state from events only (never timestamps, never
wall-clock) so that replaying the same journal twice yields identical state —
the property drills call *replay determinism*.
"""

from __future__ import annotations

from .events import read_events_safe
from .report import render_html, render_text

VIEW_TEXT = "text"
VIEW_HTML = "html"


def load_trace(path):
    """Returns ``(events, torn_tail)`` — torn tails are isolated, not dropped."""
    return read_events_safe(path)


def replay(events: list) -> dict:
    """Fold events into derived run state (pure, deterministic)."""
    st = {
        "runs_opened": 0,
        "runs_closed": 0,
        "runs_open": 0,
        "steps": 0,
        "thoughts": 0,
        "tool_calls": 0,
        "tool_results": 0,
        "tool_fails": 0,
        "redactions": 0,
        "replies": 0,
        "errors": 0,
        "budgets": 0,
        "last_reply": "",
        "final_stop": "",
    }
    for ev in events:
        p = ev.payload or {}
        t = ev.type
        if t == "run_start":
            st["runs_opened"] += 1
            st["runs_open"] += 1
        elif t == "run_end":
            st["runs_closed"] += 1
            st["runs_open"] = max(0, st["runs_open"] - 1)
            st["final_stop"] = str(p.get("stop_reason", ""))
        elif t == "step_start":
            st["steps"] += 1
        elif t == "thought":
            st["thoughts"] += 1
        elif t == "tool_call":
            st["tool_calls"] += 1
        elif t == "tool_result":
            st["tool_results"] += 1
            if p.get("ok") is False:
                st["tool_fails"] += 1
            st["redactions"] += int(p.get("redactions", 0) or 0)
        elif t == "reply":
            st["replies"] += 1
            st["last_reply"] = str(p.get("text", ""))
        elif t == "error":
            st["errors"] += 1
        elif t == "budget":
            st["budgets"] += 1
    return st


def truncate_torn_tail(path) -> bool:
    """Recovery helper: remove an undecodable trailing line (if present).

    Returns True when something was truncated. The journal stays append-only:
    only bytes *after* the last complete event line are removed.
    """
    with open(path, "rb+") as fh:
        data = fh.read()
        if not data or data.endswith(b"\n"):
            return False
        idx = data.rfind(b"\n")
        fh.truncate(idx + 1 if idx >= 0 else 0)
        return True


def text_timeline(path) -> str:
    events, _torn = load_trace(path)
    return render_text(events)


def html_report(path, title: str = "OpenAgent-X trace") -> str:
    events, _torn = load_trace(path)
    return render_html(events, title=title)


def view(events: list, which: str = VIEW_TEXT) -> str:
    """Canonical view dispatcher (kept single-source so views always agree)."""
    if which == VIEW_TEXT:
        return render_text(events)
    if which == VIEW_HTML:
        return render_html(events)
    raise ValueError(f"unknown view '{which}'")
