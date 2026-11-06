#!/usr/bin/env python3
"""X-Budget demo — a runaway agent, stopped by ceilings.

WanderLLM never finishes: it keeps calling tools forever. The budget engine
stops the run *before* costs explode, and the stop is a traced event.

    python examples/budget_demo.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openagentx.budget import Budget  # noqa: E402
from openagentx.events import EventType  # noqa: E402
from openagentx.llm import EchoLLM, LLMResponse  # noqa: E402
from openagentx.loop import AgentKernel  # noqa: E402
from openagentx.policy import default_policy  # noqa: E402
from openagentx.tools import ToolRegistry  # noqa: E402
from openagentx.builtins import register_builtins  # noqa: E402
from openagentx.trace import TraceLog  # noqa: E402


class WanderLLM(EchoLLM):
    """A model stuck in a loop: cycles through genuinely different tool
    calls (defeating similarity guards) and never replies."""

    _LOOP = [
        '{"action": {"tool": "fs_list", "args": {"path": "."}}, "thought": "survey the root"}',
        '{"action": {"tool": "fs_read", "args": {"path": "README.md"}}, "thought": "read the readme"}',
        '{"action": {"tool": "think", "args": {"note": "maybe the answer is in another directory"}}, "thought": "ponder"}',
        '{"action": {"tool": "fs_list", "args": {"path": "docs"}}, "thought": "check docs instead"}',
    ]

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, *, temperature=0.2, max_tokens=None):  # type: ignore[override]
        text = self._LOOP[self.calls % len(self._LOOP)]
        self.calls += 1
        usage = super().complete(messages, temperature=temperature, max_tokens=max_tokens).usage
        return LLMResponse(text=text, model=self.model, usage=usage)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        trace = TraceLog(path=Path(td) / "budget.jsonl")
        registry = ToolRegistry(policy=default_policy(), trace=trace)
        register_builtins(registry, include_exec=False, include_network=False)

        kernel = AgentKernel(
            WanderLLM(),
            trace,
            tools=registry,
            budget=Budget(max_iterations=5),  # the ceiling that saves the bill
        )
        result = kernel.run("List every file ever.")

        print("status     :", result.status)          # budget_exceeded
        print("iterations :", result.iterations)      # stopped at 5
        print("reply      :", result.reply)

        stops = trace.find(EventType.KERNEL_BUDGET_EXCEEDED)
        print("\nbudget events:", json.dumps([e.payload for e in stops], indent=2))


if __name__ == "__main__":
    main()
