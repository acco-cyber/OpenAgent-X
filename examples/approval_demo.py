#!/usr/bin/env python3
"""X-Consent demo — human approval as persisted state, not a chat promise.

When the policy engine returns ``ask``, the ToolRegistry refuses to act
unless an ApprovalGate says yes. This demo shows the whole consent loop,
offline and deterministic:

    1. no human wired            → ASK becomes a persisted denial (safe default)
    2. scripted human approves   → executes once; an identical replay re-asks
                                   (one-time use) and different args re-ask
                                   (hash binding)
    3. out-of-band grant         → pre-approval consumed exactly once;
                                   ttl=0 grants are already expired

    python examples/approval_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openagentx.approval import ApprovalGate, action_hash, describe_action  # noqa: E402
from openagentx.builtins import register_builtins  # noqa: E402
from openagentx.events import EventType  # noqa: E402
from openagentx.policy import default_policy  # noqa: E402
from openagentx.tools import ToolRegistry  # noqa: E402
from openagentx.trace import TraceLog  # noqa: E402


def build(gate: ApprovalGate) -> ToolRegistry:
    """Registry under the default policy (shell is ask-gated) + consent gate."""
    registry = ToolRegistry(policy=default_policy(), trace=gate.trace, confirm=gate)
    register_builtins(registry, include_exec=True, include_network=False)
    return registry


def show_verdict(label: str, observation: str) -> None:
    mark = "EXECUTED" if not observation.startswith(("[denied", "[error")) else "refused "
    print(f"  {label:34s} → {mark:8s} {observation[:64]}")


def print_audit(gate: ApprovalGate, title: str) -> None:
    print(f"\n  {title} — approval events in the trace:")
    for event in gate.trace.replay():
        if event.event_type == EventType.TASK_APPROVAL_REQUESTED:
            print(f"    requested #{event.sequence:02d} {event.payload['scope']}")
        elif event.event_type == EventType.TASK_APPROVED:
            print(f"    approved  #{event.sequence:02d} {event.payload['tool']} via {event.payload['via']}")


def print_records(gate: ApprovalGate) -> None:
    print(f"\n  persisted approval records ({gate.store_path.name}, latest snapshot per id wins):")
    for record in gate.records:
        spent = f"consumed={record.consumed_at is not None}" if record.decision == "approved" else "—"
        print(f"    {record.decision:8s} hash={record.action_hash[:12]}… {spent}")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # -- 1) nobody to ask: ASK verdicts become persisted denials --------
        print("1) no human wired — ask-gated action, nobody to approve:")
        trace1 = TraceLog(path=tmp / "consent-none.jsonl")
        gate1 = ApprovalGate(trace1, task_id="demo-1", store_dir=tmp / "approvals-1")
        registry1 = build(gate1)
        show_verdict("shell echo hi (ask, no human)", registry1.dispatch("shell", {"cmd": "echo hi"}))
        print_records(gate1)

        # -- 2) scripted human: hash binding + one-time use ------------------
        print("\n2) scripted human — approves the FIRST ask only:")
        trace2 = TraceLog(path=tmp / "consent-human.jsonl")
        answers = {"grant": 1}  # approve the FIRST ask only; every later ask is denied

        def human(tool: str, args: dict, tier: str, reason: str) -> bool:
            approved = answers["grant"] > 0
            answers["grant"] -= 1
            print(f"    human asked to approve {describe_action(tool, args)} — {'yes' if approved else 'NO'}")
            return approved

        gate2 = ApprovalGate(trace2, task_id="demo-2", human=human, store_dir=tmp / "approvals-2")
        registry2 = build(gate2)
        show_verdict("shell echo hi (ask → approved)", registry2.dispatch("shell", {"cmd": "echo hi"}))
        show_verdict("shell echo hi (exact replay)", registry2.dispatch("shell", {"cmd": "echo hi"}))
        show_verdict("shell echo bye (different args)", registry2.dispatch("shell", {"cmd": "echo bye"}))
        print_records(gate2)
        print_audit(gate2, "audit trail")

        # -- 3) out-of-band grants: pre-approval and expiry ------------------
        print("\n3) out-of-band grant() — approval captured outside the loop:")
        trace3 = TraceLog(path=tmp / "consent-grant.jsonl")
        gate3 = ApprovalGate(trace3, task_id="demo-3", human=None, store_dir=tmp / "approvals-3")
        registry3 = build(gate3)
        gate3.grant("shell", {"cmd": "echo pre-approved"}, "P2")     # human clicks "allow" in a UI
        gate3.grant("shell", {"cmd": "echo stale"}, "P2", ttl_seconds=0)  # granted, already stale
        show_verdict("shell echo pre-approved (grant)", registry3.dispatch("shell", {"cmd": "echo pre-approved"}))
        show_verdict("shell echo pre-approved (replay)", registry3.dispatch("shell", {"cmd": "echo pre-approved"}))
        show_verdict("shell echo stale (ttl=0)", registry3.dispatch("shell", {"cmd": "echo stale"}))
        print_audit(gate3, "audit trail")

        print("\nreplay any of this with: python -m openagentx.cli trace <trace file>")


if __name__ == "__main__":
    main()
