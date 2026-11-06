"""X-Consent: human approval as persisted state — never a chat promise.

Closes the loop that X-Guard opens: when the policy engine returns ``ask``,
:class:`ToolRegistry` refuses to act unless a confirm callback says yes.
Until now that callback was an ad-hoc ``bool``. This module makes the
approval **state**, aligned with ``schemas/approval.schema.json``:

* **Hash-bound** — an approval authorizes one exact action: the SHA-256 of
  canonical ``{"tool", "tier", "args"}`` JSON. The same tool with different
  args is a *different* action and must be asked again ("approve what you
  saw, get what you approved").
* **One-time** — spending an approval on an execution consumes it, so a
  looping model cannot replay a previously approved side effect.
* **Expiring** — every record carries ``expires_at``; stale approvals
  authorize nothing (TTL is a ceiling on how long a human's yes stays true).
* **Event-before-effect** — ``task.approval_requested`` is persisted before
  the human is asked; ``task.approved`` is persisted before the action runs.
* **Files over databases** — records append as JSONL under
  ``.openagentx/approvals/``: grep-able, diffable, one snapshot per line,
  latest snapshot per ``approval_id`` wins.

Drop-in design: :meth:`ApprovalGate.confirm` matches ``ToolRegistry``'s
``ConfirmFn`` signature, so wiring consent is one constructor argument —
``ToolRegistry(policy=…, trace=…, confirm=ApprovalGate(trace, human=…))`` —
and the kernel, policy engine, and tools stay untouched.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from openagentx.events import EventType, utc_now_iso
from openagentx.trace import TraceLog

DEFAULT_APPROVAL_DIR = ".openagentx/approvals"

#: ``(tool, args, tier, reason) -> bool`` — identical to ``ToolRegistry.ConfirmFn``.
HumanDecision = Callable[[str, dict[str, Any], str, str], bool]


def action_hash(tool: str, tier: str, args: dict[str, Any]) -> str:
    """SHA-256 over the canonical form of the exact action being approved.

    Canonical = sorted keys, no whitespace, UTF-8 — so the same action
    hashes identically across processes and platforms, and any argument
    difference produces a different hash.
    """
    canonical = json.dumps(
        {"tool": tool, "tier": tier, "args": args},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def describe_action(tool: str, args: dict[str, Any]) -> str:
    """One-line human-readable scope of what is being approved."""
    rendered = ", ".join(f"{k}={str(v)[:60]!r}" for k, v in sorted(args.items()))
    return f"{tool}({rendered or 'no args'})"


@dataclass
class ApprovalRecord:
    """One persisted human decision. Mirrors ``approval.schema.json`` plus
    one kernel extension: ``consumed_at`` (the one-time-use marker)."""

    action_hash: str
    decision: str                          # approved | denied
    task_id: str | None = None
    approval_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    approver_id: str | None = None
    scope: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    expires_at: str = ""
    consumed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "task_id": self.task_id,
            "action_hash": self.action_hash,
            "approver_id": self.approver_id,
            "decision": self.decision,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "consumed_at": self.consumed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRecord":
        return cls(
            action_hash=data["action_hash"],
            decision=data["decision"],
            task_id=data.get("task_id"),
            approval_id=data.get("approval_id", str(uuid.uuid4())),
            approver_id=data.get("approver_id"),
            scope=data.get("scope", ""),
            created_at=data.get("created_at", utc_now_iso()),
            expires_at=data.get("expires_at", ""),
            consumed_at=data.get("consumed_at"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    # ------------------------------------------------------------- validity

    def _expires_dt(self) -> datetime:
        try:
            return datetime.fromisoformat(self.expires_at)
        except (TypeError, ValueError):
            return datetime.fromtimestamp(0, tz=timezone.utc)  # unparseable = already stale

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now >= self._expires_dt()  # strict: ttl=0 means instantly expired

    def authorizes(self, hash_hex: str, now: datetime | None = None) -> bool:
        """True when this record can still be spent on the exact action."""
        return (
            self.decision == "approved"
            and self.action_hash == hash_hex
            and self.consumed_at is None
            and not self.is_expired(now)
        )


class ApprovalGate:
    """The ``confirm`` seam that turns ASK verdicts into auditable consent.

    Args:
        trace: the run's event log (``task.approval_requested`` /
            ``task.approved`` are persisted here).
        task_id: optional task the approvals belong to.
        human: ``(tool, args, tier, reason) -> bool``. ``None`` means nobody
            is available to approve — every ASK becomes a persisted denial,
            which is the safe default.
        ttl_seconds: how long a granted approval stays valid (default 5 min).
        approver_id: recorded on records created by the ``human`` callback.
        store_dir: where approval JSONL files append. Pass a temp dir in
            tests/demos; defaults to ``.openagentx/approvals/``.
    """

    def __init__(
        self,
        trace: TraceLog,
        *,
        task_id: str | None = None,
        human: HumanDecision | None = None,
        ttl_seconds: int = 300,
        approver_id: str = "human",
        store_dir: str | Path | None = None,
    ) -> None:
        self.trace = trace
        self.task_id = task_id
        self.human = human
        self.ttl_seconds = ttl_seconds
        self.approver_id = approver_id
        directory = Path(store_dir) if store_dir else Path(DEFAULT_APPROVAL_DIR)
        self.store_path = directory / f"{task_id or 'adhoc'}.jsonl"
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[ApprovalRecord] = []  # in-memory view; file is the truth

    # ------------------------------------------------------------------ seam

    def __call__(self, tool: str, args: dict[str, Any], tier: str, reason: str) -> bool:
        """Alias so the gate itself can be passed as ``ToolRegistry(confirm=gate)``."""
        return self.confirm(tool, args, tier, reason)

    def confirm(self, tool: str, args: dict[str, Any], tier: str, reason: str) -> bool:
        """Spend an existing valid approval or obtain one from the human."""
        hash_hex = action_hash(tool, tier, args)

        # 1) out-of-band pre-approval (grant()) covering this exact action?
        prior = next((r for r in self.records if r.authorizes(hash_hex)), None)
        if prior is not None:
            return self._spend(prior, tool, tier, via="pre-approval")

        # 2) event-before-effect: persist the request before asking.
        expires_at = self._expires_iso()
        self.trace.append(
            EventType.TASK_APPROVAL_REQUESTED,
            task_id=self.task_id,
            actor_type="user",
            actor_id="approval-gate",
            tool=tool,
            tier=tier,
            action_hash=hash_hex,
            scope=describe_action(tool, args),
            reason=reason,
            expires_at=expires_at,
        )

        granted = bool(self.human(tool, args, tier, reason)) if self.human else False
        record = ApprovalRecord(
            action_hash=hash_hex,
            decision="approved" if granted else "denied",
            task_id=self.task_id,
            approver_id=self.approver_id if granted else None,
            scope=describe_action(tool, args),
            expires_at=expires_at,
            consumed_at=utc_now_iso() if granted else None,  # granted = spent on this call
        )
        self._persist(record)
        if not granted:
            return False
        return self._spend(record, tool, tier, via="live-human", already_consumed=True)

    # --------------------------------------------------------------- grants

    def grant(
        self,
        tool: str,
        args: dict[str, Any],
        tier: str,
        *,
        approver_id: str = "human",
        ttl_seconds: int | None = None,
    ) -> ApprovalRecord:
        """Record an out-of-band approval for one exact, not-yet-executed action.

        The UI/service layer calls this when the human says yes outside the
        kernel loop (a dashboard button, a CLI prompt); the next
        :meth:`confirm` with a matching action hash spends it. Validity uses
        the same TTL rule — ``ttl_seconds=0`` yields an approval that is
        already stale on inspection (useful for expiry tests/demos).
        """
        record = ApprovalRecord(
            action_hash=action_hash(tool, tier, args),
            decision="approved",
            task_id=self.task_id,
            approver_id=approver_id,
            scope=describe_action(tool, args),
            expires_at=self._expires_iso(ttl_seconds),
        )
        self._persist(record)
        return record

    # -------------------------------------------------------------- private

    def _spend(
        self,
        record: ApprovalRecord,
        tool: str,
        tier: str,
        *,
        via: str,
        already_consumed: bool = False,
    ) -> bool:
        """Mark an approval spent, persist it, emit ``task.approved``."""
        if not already_consumed:
            record.consumed_at = utc_now_iso()
            self._persist(record)  # latest snapshot per approval_id wins
        self.trace.append(
            EventType.TASK_APPROVED,
            task_id=self.task_id,
            actor_type="user",
            actor_id=record.approver_id or "approval-gate",
            tool=tool,
            tier=tier,
            approval_id=record.approval_id,
            action_hash=record.action_hash,
            via=via,
            consumed=True,
        )
        return True

    def _expires_iso(self, ttl_seconds: int | None = None) -> str:
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        return (
            datetime.now(timezone.utc) + timedelta(seconds=ttl)
        ).isoformat(timespec="milliseconds")

    def _persist(self, record: ApprovalRecord) -> None:
        self.records.append(record)
        with self.store_path.open("a", encoding="utf-8") as fh:
            fh.write(record.to_json() + "\n")
