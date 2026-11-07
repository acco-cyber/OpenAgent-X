"""Replay from any point — the journal folds from the middle, honestly.

Event sourcing means derived state is a deterministic fold over events.
``trace.replay`` folds a whole journal; :func:`replay_from` folds a
**suffix**: every event with ``seq >= from_seq``, starting the fold from
zero at that point. This is how you answer "what did the rest of the run
do?" without pretending the prefix never happened.

Contracts (all enforced, none assumed):

- **Honest bounds**: ``from_seq`` must satisfy ``0 <= from_seq <= max
  seq`` of the recovered journal; an empty journal exposes exactly one
  valid window — ``0``, the zero state. Out-of-bounds raises
  ``ValueError``, never silent clamping.
- **Density required**: the journal's seqs must be contiguous from first
  to last — a gapped journal is an integrity failure, not a state to
  fold (same rule the snapshot module enforces for prefixes, applied to
  the whole stream the suffix draws from).
- **Additive where honest**: every monotone counter of the suffix fold
  equals the whole-run counter minus the prefix counter — but the module
  never claims additivity for the fields where it is false
  (``runs_open`` is clamped, ``last_reply``/``final_stop`` describe only
  their own window). The drill proves both halves of that sentence.
- **Torn-tail isolation**: a crash-torn trailing line is invisible to
  the fold and reported, never folded.
- **The view cannot leak**: the state is the view, and the view renders
  through the redaction engine — a raw secret on disk (the disk is the
  truth) never leaves the module, even inside ``last_reply``.
- Everything is deterministic: no timestamps, no wall-clock — same
  journal and window, same bytes out.
"""

from __future__ import annotations

from .redact import redact
from .trace import load_trace, replay

_ZERO_STATE_KEYS = (
    "budgets", "errors", "final_stop", "last_reply", "redactions",
    "replies", "runs_closed", "runs_open", "runs_opened", "steps",
    "thoughts", "tool_calls", "tool_fails", "tool_results",
)


def _redact_state(state: dict) -> tuple:
    """Redact the free-text state fields; returns (safe state, count)."""
    n = 0
    safe = dict(state)
    for key in ("last_reply", "final_stop"):
        text, k = redact(str(safe.get(key, "")))
        safe[key] = text
        n += k
    return safe, n


def replay_from(path: str, from_seq: int = 0) -> dict:
    """Fold the journal suffix ``seq >= from_seq`` into derived state.

    Bounds and density are enforced honestly (``ValueError`` on
    violation). Returns the report dict: the window, the folded and
    total event counts, the torn-tail flag, the **redacted** state fold
    and the view's own redaction count.
    """
    from_seq = int(from_seq)
    events, torn = load_trace(path)
    max_seq = events[-1].seq if events else 0
    if from_seq < 0 or from_seq > max_seq:
        raise ValueError(
            f"journal {path}: from_seq {from_seq} outside 0..{max_seq}")
    seqs = [ev.seq for ev in events]
    if seqs and seqs != list(range(seqs[0], seqs[0] + len(seqs))):
        raise ValueError(f"journal {path}: gap in the event stream "
                         f"(seqs {seqs[0]}..{seqs[-1]} are not contiguous)")
    suffix = [ev for ev in events if ev.seq >= from_seq]
    state, n_red = _redact_state(replay(suffix))
    return {
        "from_seq": from_seq,
        "folded": len(suffix),
        "total": len(events),
        "torn_tail": bool(torn),
        "state": state,
        "view_redactions": n_red,
    }


def render_replay(report: dict) -> str:
    """Deterministic text render: a header naming the window, then the
    state keys sorted alphabetically. No timestamps anywhere."""
    head = (f"replay --from {report['from_seq']}: "
            f"folded {report['folded']} of {report['total']} events")
    if report["torn_tail"]:
        head += " [torn tail isolated]"
    lines = [head]
    state = report["state"]
    for key in sorted(state):
        lines.append(f"{key}: {state[key]}")
    return "\n".join(lines) + "\n"
