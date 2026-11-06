#!/usr/bin/env python3
"""X-Guard demo — the policy engine decides, not the prompt.

Under the default policy: reads are allowed, writes return diffs, shell
execution is ask-gated (and denied when no human confirms), and denied
tools vanish from the prompt surface.

    python examples/policy_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openagentx.events import EventType  # noqa: E402
from openagentx.policy import default_policy, ActionContext, Tier  # noqa: E402
from openagentx.tools import ToolRegistry  # noqa: E402
from openagentx.builtins import register_builtins  # noqa: E402
from openagentx.trace import TraceLog  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        trace = TraceLog(path=Path(td) / "policy.jsonl")
        policy = default_policy()
        # no confirm callback = nobody to approve ASK verdicts → they get denied
        registry = ToolRegistry(policy=policy, trace=trace)
        register_builtins(registry, include_exec=True, include_network=False)

        print("1) read allowed   :", registry.dispatch("fs_list", {"path": "."})[:60])
        print("2) write + diff   :", registry.dispatch("fs_write", {"path": "notes.txt", "content": "hello"})[:60])
        print("3) shell ask-gated:", registry.dispatch("shell", {"cmd": "echo hi"})[:80])
        print("4) unknown tool   :", registry.dispatch("rm_rf", {})[:80])

        print("\npolicy.decision events (audit trail):")
        for event in trace.find(EventType.POLICY_DECISION):
            print(f"  {event.payload['tool']:12s} tier={event.payload['tier']} → {event.payload['verdict']} ({event.payload['rule_id']})")

        print("\nprompt surface — denied tools vanish (capability-text pruning):")
        section = registry.prompt_section()
        for tool_name in ("fs_read", "fs_write", "shell"):
            visible = tool_name in section
            verdict = policy.evaluate(ActionContext(tool=tool_name, tier=Tier.P2 if tool_name == "shell" else Tier.P1))
            print(f"  {tool_name:10s} verdict={verdict.verdict:5s} visible={visible}")


if __name__ == "__main__":
    main()
