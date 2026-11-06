"""X-Trace: event envelopes aligned with ``schemas/event-envelope.schema.json``.

Every observable thing that happens during a run is persisted as an
append-only ``EventEnvelope`` **before** the side effect it describes is
attempted (event-before-effect rule). This makes any run replayable,
auditable, and resumable.

Extension rule: the JSON Schema enumerates a fixed set of ``event_type``
values. The reference kernel extends that enum with **namespaced** types
(``kernel.*``, ``tool.*``, ``mem.*``). New types must always carry a
namespace so upstream schema evolution stays mechanical.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator


class EventType:
    """Event type constants. Schema-enum values first, kernel extensions after."""

    # --- values defined in schemas/event-envelope.schema.json ---
    TASK_CREATED = "task.created"
    TASK_PLANNED = "task.planned"
    TASK_APPROVAL_REQUESTED = "task.approval_requested"
    TASK_APPROVED = "task.approved"
    TASK_STARTED = "task.started"
    TASK_WAITING_FOR_USER = "task.waiting_for_user"
    TASK_BLOCKED = "task.blocked"
    TASK_RECOVERED = "task.recovered"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    SUBTASK_DISPATCHED = "subtask.dispatched"
    SUBTASK_COMPLETED = "subtask.completed"
    SUBTASK_FAILED = "subtask.failed"
    AGENT_STARTED = "agent.started"
    AGENT_MODEL_SELECTED = "agent.model_selected"
    AGENT_TOOL_CALL_STARTED = "agent.tool_call.started"
    AGENT_TOOL_CALL_COMPLETED = "agent.tool_call.completed"
    EXECUTION_WORKSPACE_CREATED = "execution.workspace_created"
    EXECUTION_SNAPSHOT_CREATED = "execution.snapshot_created"
    EXECUTION_TERMINATED = "execution.terminated"
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_DOWNLOADED = "artifact.downloaded"
    MEMORY_CANDIDATE_CREATED = "memory.candidate_created"
    MEMORY_PROMOTED = "memory.promoted"

    # --- kernel extension types (namespaced) ---
    KERNEL_ITERATION = "kernel.iteration"
    KERNEL_DEGENERACY = "kernel.degeneracy_detected"
    KERNEL_BUDGET_EXCEEDED = "kernel.budget_exceeded"
    KERNEL_STOPPED = "kernel.stopped"
    PROMPT_COMPILED = "kernel.prompt_compiled"
    POLICY_DECISION = "policy.decision"
    MEM_RECALLED = "mem.recalled"
    MEM_SUPERSEDED = "mem.superseded"
    PACK_ACTIVATED = "pack.activated"


@dataclass(frozen=True)
class Actor:
    """Who caused an event. Mirrors the schema's ``actor`` object."""

    type: str  # user | agent | system | runtime | policy
    id: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "id": self.id}


# Patterns whose matches are replaced before an event is persisted.
# Defense in depth: the schema states "secrets must be redacted before
# persistence", so the kernel does it automatically at the trace boundary.
_REDACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),           # GitHub PATs
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),   # fine-grained GitHub PATs
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),          # OpenAI-style keys
    re.compile(r"AKIA[0-9A-Z]{16}"),               # AWS access keys
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),   # Slack tokens
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),   # bearer headers
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S{8,}"),
)

_REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Recursively redact secret-looking strings inside ``value``."""
    if isinstance(value, str):
        out = value
        for pattern in _REDACTION_PATTERNS:
            out = pattern.sub(_REDACTED, out)
        return out
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with timezone info."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class EventEnvelope:
    """One append-only workflow event.

    Field names and semantics mirror ``schemas/event-envelope.schema.json``
    so kernel traces validate against the universal contract.
    """

    event_type: str
    task_id: str | None
    sequence: int
    actor: Actor
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=utc_now_iso)
    correlation_id: str | None = None
    redaction_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializable form, with payload secrets redacted on the way out."""
        payload = redact(self.payload)
        redacted = payload != self.payload
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "actor": self.actor.to_dict(),
            "correlation_id": self.correlation_id,
            "payload": payload,
            "redaction_applied": redacted or self.redaction_applied,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventEnvelope":
        actor = Actor(type=data["actor"]["type"], id=data["actor"]["id"])
        return cls(
            event_type=data["event_type"],
            task_id=data.get("task_id"),
            sequence=int(data["sequence"]),
            actor=actor,
            payload=dict(data.get("payload") or {}),
            event_id=data.get("event_id", str(uuid.uuid4())),
            occurred_at=data.get("occurred_at", utc_now_iso()),
            correlation_id=data.get("correlation_id"),
            redaction_applied=bool(data.get("redaction_applied", False)),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> "EventEnvelope":
        return cls.from_dict(json.loads(line))


def iter_envelopes(lines: Iterator[str]) -> Iterator[EventEnvelope]:
    """Parse a stream of JSONL lines into envelopes, skipping blank lines."""
    for line in lines:
        line = line.strip()
        if line:
            yield EventEnvelope.from_json(line)
