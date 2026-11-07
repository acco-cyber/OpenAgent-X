"""Snapshot travel: derived state at any checkpoint of the event stream.

Event sourcing buys time travel, and this module cashes it in. A
**checkpoint** is a sequence number; the **snapshot** at a checkpoint is the
pure :func:`~openagentx.trace.replay` fold over the event *prefix* with
``seq <= checkpoint``. :func:`travel` evaluates an ascending list of
checkpoints in one deterministic pass.

Contracts (all enforced, none assumed):

- **Prefix purity**: a snapshot depends only on events with
  ``seq <= checkpoint``. Later events — appended corrections, extra steps,
  whole new runs — cannot rewrite history at an earlier checkpoint.
- **Torn-tail isolation**: a crash-torn trailing line is invisible to every
  checkpoint that precedes it; travel over the recovered journal matches
  travel over the intact prefix.
- **Honest bounds**: checkpoints must be strictly ascending integers within
  the journal (``0``..``max seq``); an empty journal exposes exactly one
  checkpoint — ``0``, the zero state. Violations raise ``ValueError``, never
  silent clamping.
- **Density required**: the folded prefix must be a dense ``0..k`` sequence —
  a gapped journal is an integrity failure, not a state to fold.
- Everything is a plain dict of ints/strings: snapshots compare with ``==``
  and travel is idempotent.

Example:

    >>> from openagentx.events import Event
    >>> e = Event(seq=0, run_id="r", ts=1.0, type="run_start", payload={"task": "t"})
    >>> snapshot_at([e], 0)["state"]["runs_open"]
    1
    >>> snapshot_at([], 0)["state"] == ZERO_STATE
    True
"""

from __future__ import annotations

from .trace import replay

ZERO_STATE = {
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


def _journal_end(events: list) -> int:
    return max((e.seq for e in events), default=0)


def _require_dense(prefix: list) -> None:
    seqs = [e.seq for e in prefix]
    if seqs != list(range(len(seqs))):
        raise ValueError(
            f"journal prefix is not dense: {len(seqs)} events, "
            f"seqs {seqs[:3]}...{seqs[-3:] if len(seqs) > 3 else ''}")


def snapshot_at(events: list, seq: int) -> dict:
    """Derived state after folding every event with ``seq <= seq``.

    Pure prefix fold: later events cannot change it, so appending to the
    journal never rewrites an earlier snapshot.
    """
    seq = int(seq)
    if seq < 0:
        raise ValueError(f"checkpoint must be >= 0, got {seq}")
    end = _journal_end(events)
    if seq > end:
        raise ValueError(f"checkpoint {seq} beyond journal end {end}")
    prefix = [e for e in events if e.seq <= seq]
    _require_dense(prefix)
    return {"seq": seq, "state": replay(prefix)}


def travel(events: list, checkpoints) -> list:
    """Snapshots at an ascending list of checkpoints (pure, deterministic).

    ``checkpoints`` must be a non-empty, strictly ascending sequence of
    integers within the journal; anything else raises ``ValueError``.
    """
    pts = [int(c) for c in checkpoints]
    if not pts:
        raise ValueError("travel needs at least one checkpoint")
    for a, b in zip(pts, pts[1:]):
        if b <= a:
            raise ValueError(
                f"checkpoints must be strictly ascending, got ...{a}, {b}")
    return [snapshot_at(events, c) for c in pts]


def monotone(states: list) -> bool:
    """True when folded counters never decrease across checkpoints."""
    keys = ("runs_opened", "steps", "thoughts", "tool_calls", "tool_results",
            "replies", "errors")
    for a, b in zip(states, states[1:]):
        for k in keys:
            if b["state"][k] < a["state"][k]:
                return False
    return True
