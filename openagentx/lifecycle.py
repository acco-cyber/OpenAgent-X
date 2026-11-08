"""Canonical task lifecycle — the blueprint's durable task machine, as code.

Ported from the HYDRION ONE blueprint, section 5 (``docs/blueprint/
02-architecture.md``): a durable task lifecycle where every transition is
persisted, retries are bounded, and terminal states are frozen.  The state
machine is deliberately small and deterministic — the orchestrator owns
state transitions, the model only proposes them.

Contracts enforced here:

- **Eleven canonical states** with an exact legal-transition table
  (``TRANSITIONS``).  ``COMPLETED``/``FAILED``/``CANCELLED`` are terminal:
  zero outgoing transitions, and the *only* zero-out states.
- **Approval is bound to the exact plan hash** (blueprint: "Approval is
  bound to the exact action/plan version").  ``approve(plan)`` records the
  SHA-256 of the canonical plan JSON; leaving ``APPROVED`` through
  ``start(plan)`` requires the *same* plan object content — a different
  payload raises :class:`ApprovalMismatch` and appends nothing.
- **Append-only, dense journal.**  Every observable move is an
  :class:`~openagentx.events.Event` with a dense sequence — the same journal
  contract as agent runs.  Reasons and notes cross the redaction boundary
  (``redact_obj``) before they are journaled, so a secret typed into a
  reason dies at the boundary like any tool payload.
- **Terminal does not mean silent.**  ``CANCELLED`` and ``FAILED`` still
  accept ``record_cleanup`` events — blueprint: "Terminal; cleanup and audit
  still run."  Cleanup outside a terminal state is refused.
- **Replay is a pure fold.**  ``TaskLifecycle.replay(events)`` rebuilds the
  machine from its journal; the rebuilt machine's ``render()`` is
  byte-identical to the original's (renders carry no wall-clock).

Example (a happy path and a loud refusal):

    >>> from openagentx.lifecycle import TaskLifecycle
    >>> m = TaskLifecycle("t-1")
    >>> m.state
    'CREATED'
    >>> _ = m.transition("PLANNED", reason="plan validated")
    >>> m.state
    'PLANNED'
    >>> m.transition("COMPLETED")
    Traceback (most recent call last):
        ...
    openagentx.lifecycle.IllegalTransition: no legal transition PLANNED -> COMPLETED (allowed: APPROVED, RUNNING, WAITING_FOR_USER)

Approval binds to the exact plan content:

    >>> m2 = TaskLifecycle("t-2")
    >>> plan = {"objective": "sourced report"}
    >>> _ = m2.transition("PLANNED")
    >>> _ = m2.approve(plan, actor="human")
    >>> m2.start({"objective": "a different plan"})
    Traceback (most recent call last):
        ...
    openagentx.lifecycle.ApprovalMismatch: approval is bound to the exact plan hash; the passed plan does not match the approved plan
    >>> _ = m2.start(plan)
    >>> m2.state
    'RUNNING'
"""

from __future__ import annotations

import hashlib
import json
import time

from .events import Event, Journal
from .redact import redact_obj

CREATED = "CREATED"
PLANNED = "PLANNED"
APPROVED = "APPROVED"
RUNNING = "RUNNING"
VERIFYING = "VERIFYING"
WAITING_FOR_USER = "WAITING_FOR_USER"
BLOCKED = "BLOCKED"
RECOVERY = "RECOVERY"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

#: The eleven canonical task states (blueprint §5 table, verbatim).
CANONICAL_STATES: tuple = (
    CREATED, PLANNED, APPROVED, RUNNING, VERIFYING,
    WAITING_FOR_USER, BLOCKED, RECOVERY,
    COMPLETED, FAILED, CANCELLED,
)

#: Terminal states — zero outgoing transitions, cleanup still recorded.
TERMINAL_STATES = frozenset({COMPLETED, FAILED, CANCELLED})

#: The exact legal-transition table from blueprint §5.  Guarded by golden
#: task 47 (``transitions_match_blueprint``): a drift from the documented
#: table is a failing check, not a doc rot.
TRANSITIONS: dict = {
    CREATED: frozenset({PLANNED, CANCELLED, FAILED}),
    PLANNED: frozenset({APPROVED, RUNNING, WAITING_FOR_USER}),
    APPROVED: frozenset({RUNNING, CANCELLED}),
    RUNNING: frozenset({VERIFYING, WAITING_FOR_USER, BLOCKED, FAILED,
                        CANCELLED, RECOVERY}),
    VERIFYING: frozenset({COMPLETED, RECOVERY, BLOCKED, FAILED}),
    WAITING_FOR_USER: frozenset({APPROVED, RUNNING, CANCELLED}),
    BLOCKED: frozenset({RUNNING, CANCELLED, FAILED}),
    RECOVERY: frozenset({RUNNING, BLOCKED, FAILED}),
    COMPLETED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}


class LifecycleError(Exception):
    """Base class for lifecycle contract violations."""


class IllegalTransition(LifecycleError):
    """A state move outside the canonical transition table."""


class ApprovalMismatch(LifecycleError):
    """The passed plan does not match the approved plan hash."""


def plan_hash(plan: dict) -> str:
    """SHA-256 over the canonical (sort_keys, compact) JSON of *plan*.

    Key order is irrelevant; any content change changes the hash — the
    property that makes an approval bound to "the exact action/plan version".

    >>> plan_hash({"b": 1, "a": 2}) == plan_hash({"a": 2, "b": 1})
    True
    >>> plan_hash({"a": 2}) != plan_hash({"a": 3})
    True
    """
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TaskLifecycle:
    """Event-sourced task state machine over the blueprint §5 table.

    Events go to a real :class:`~openagentx.events.Journal` when *journal*
    is given (durable, on disk, dense seq) or to an in-memory event list
    otherwise — both paths produce the same :class:`Event` objects and the
    same replay.
    """

    def __init__(self, task_id: str, journal: Journal | None = None):
        self.task_id = str(task_id)
        self._journal = journal
        self._events: list = []
        self._seq = 0
        self._state = CREATED
        self._approved_hash: str | None = None
        self._cleanups = 0
        self._append("lifecycle_created", {"task_id": self.task_id})

    # -- event plumbing ----------------------------------------------------

    def _append(self, ev_type: str, payload: dict) -> Event:
        red, _n = redact_obj(dict(payload))
        ev = Event(seq=self._seq, run_id=self.task_id, type=ev_type,
                   payload=red, ts=time.time())
        self._seq += 1
        if self._journal is not None:
            self._journal.append(ev_type, red)
            # the durable journal owns its own seq numbering; keep the
            # in-memory mirror dense from zero for replay/render parity
            self._events.append(Event(
                seq=len(self._events), run_id=self.task_id, type=ev_type,
                payload=red, ts=ev.ts))
        else:
            self._events.append(ev)
        return ev

    @property
    def events(self) -> tuple:
        """The append-only event log as an immutable tuple."""
        return tuple(self._events)

    @property
    def state(self) -> str:
        return self._state

    @property
    def approved_hash(self):
        return self._approved_hash

    @property
    def cleanups(self) -> int:
        return self._cleanups

    def can(self, to_state: str) -> bool:
        return to_state in TRANSITIONS[self._state]

    # -- the guarded moves ---------------------------------------------------

    def transition(self, to_state: str, reason: str = "",
                   actor: str = "", pre_approved: bool = False) -> Event:
        """Move to *to_state* if the table allows it; refuse loudly otherwise.

        A refused move appends nothing and leaves the state unchanged — a
        rejected transition is not an event, it is an exception.
        """
        if to_state not in CANONICAL_STATES:
            raise IllegalTransition(f"unknown state {to_state!r}")
        if to_state not in TRANSITIONS[self._state]:
            allowed = ", ".join(sorted(TRANSITIONS[self._state]))
            raise IllegalTransition(
                f"no legal transition {self._state} -> {to_state} "
                f"(allowed: {allowed})")
        ev = self._append("lifecycle_transition", {
            "from": self._state,
            "to": to_state,
            "actor": actor,
            "reason": reason,
            "pre_approved": bool(pre_approved),
        })
        self._state = to_state
        return ev

    def approve(self, plan: dict, actor: str = "human") -> Event:
        """Capture approval bound to the exact plan hash (blueprint §5.7)."""
        if not isinstance(plan, dict):
            raise LifecycleError("plan must be a dict to be hash-bound")
        ev = self.transition(APPROVED, reason="approval captured",
                             actor=actor)
        self._approved_hash = plan_hash(plan)
        self._append("lifecycle_approval", {"action_hash": self._approved_hash})
        return ev

    def start(self, plan: dict | None = None, actor: str = "agent") -> Event:
        """Leave APPROVED via the hash-bound plan, or PLANNED pre-approved."""
        if self._state == APPROVED:
            if plan is None:
                raise ApprovalMismatch(
                    "approval is bound to the exact plan hash; "
                    "pass the approved plan to start()")
            if plan_hash(plan) != self._approved_hash:
                raise ApprovalMismatch(
                    "approval is bound to the exact plan hash; "
                    "the passed plan does not match the approved plan")
            return self.transition(RUNNING, reason="approved plan started",
                                   actor=actor)
        return self.transition(RUNNING, reason="pre-approved low-risk start",
                               actor=actor, pre_approved=True)

    def cancel(self, reason: str = "", actor: str = "user") -> Event:
        """User or policy stopped the task (legal moves only, per the table)."""
        return self.transition(CANCELLED, reason=reason, actor=actor)

    def record_cleanup(self, note: str = "") -> Event:
        """Terminal-state audit hook: cleanup and audit still run (§5)."""
        if self._state not in TERMINAL_STATES:
            raise LifecycleError(
                f"cleanup records belong to terminal states; "
                f"{self._state} is not terminal")
        self._cleanups += 1
        return self._append("lifecycle_cleanup", {"note": note})

    # -- folds and renders ---------------------------------------------------

    def render(self) -> str:
        """Byte-deterministic journal render (no wall-clock, no secrets)."""
        lines = []
        for ev in self._events:
            if ev.type == "lifecycle_transition":
                p = ev.payload
                lines.append(
                    f"{ev.seq:03d} {p.get('from')}->{p.get('to')}"
                    f" actor={p.get('actor', '')}"
                    f" reason={p.get('reason', '')}")
            elif ev.type == "lifecycle_created":
                lines.append(f"{ev.seq:03d} created task={ev.payload.get('task_id')}")
            elif ev.type == "lifecycle_approval":
                lines.append(f"{ev.seq:03d} approval hash={ev.payload.get('action_hash')}")
            elif ev.type == "lifecycle_cleanup":
                lines.append(f"{ev.seq:03d} cleanup note={ev.payload.get('note', '')}")
            else:
                lines.append(f"{ev.seq:03d} {ev.type}")
        return "\n".join(lines) + "\n"

    @classmethod
    def replay(cls, events) -> "TaskLifecycle":
        """Pure fold: rebuild the machine from its event log.

        Every replayed move is re-validated against the transition table —
        replaying a corrupted log raises, it never launders.
        """
        m = cls.__new__(cls)
        m.task_id = "replayed"
        m._journal = None
        m._events = []
        m._seq = 0
        m._state = None
        m._approved_hash = None
        m._cleanups = 0
        for ev in events:
            if ev.type == "lifecycle_created":
                m.task_id = str(ev.payload.get("task_id", "replayed"))
                m._state = CREATED
                m._append("lifecycle_created", {"task_id": m.task_id})
            elif ev.type == "lifecycle_transition":
                if m._state is None:
                    raise LifecycleError("transition before lifecycle_created")
                m.transition(ev.payload.get("to", ""),
                             reason=str(ev.payload.get("reason", "")),
                             actor=str(ev.payload.get("actor", "")),
                             pre_approved=bool(ev.payload.get("pre_approved")))
            elif ev.type == "lifecycle_approval":
                m._approved_hash = str(ev.payload.get("action_hash"))
                m._append("lifecycle_approval",
                          {"action_hash": m._approved_hash})
            elif ev.type == "lifecycle_cleanup":
                m._cleanups += 1
                m._append("lifecycle_cleanup",
                          {"note": str(ev.payload.get("note", ""))})
            else:
                raise LifecycleError(f"unknown lifecycle event {ev.type!r}")
        if m._state is None:
            raise LifecycleError("empty replay: no lifecycle_created event")
        return m
