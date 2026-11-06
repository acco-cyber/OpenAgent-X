#!/usr/bin/env python3
"""Hello, agent — the 60-second OpenAgent-X tour.

Runs the full kernel offline (EchoLLM: zero API keys) and prints the
resulting run summary and trace file.

    python examples/hello_agent.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openagentx.budget import Budget  # noqa: E402
from openagentx.llm import EchoLLM  # noqa: E402
from openagentx.loop import AgentKernel  # noqa: E402
from openagentx.policy import default_policy  # noqa: E402
from openagentx.tools import ToolRegistry  # noqa: E402
from openagentx.builtins import register_builtins  # noqa: E402
from openagentx.trace import TraceLog  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        trace = TraceLog(path=Path(td) / "hello.jsonl")
        policy = default_policy()
        registry = ToolRegistry(policy=policy, trace=trace)
        register_builtins(registry, include_exec=False, include_network=False)

        kernel = AgentKernel(
            EchoLLM(),                       # deterministic offline model
            trace,
            tools=registry,
            budget=Budget(max_iterations=4),
        )
        result = kernel.run("Summarize the files in this workspace and finish.")

        print("status     :", result.status)
        print("iterations :", result.iterations)
        print("tokens     :", result.usage["total_tokens"])
        print("model      :", result.model)
        print("\nreply:\n", result.reply)

        summary = trace.summary()
        print(f"\ntrace: {summary['events']} events in {summary['file']}")
        for event_type, count in summary["by_type"].items():
            print(f"  {count:3d} × {event_type}")

        # Every event is a plain JSON envelope — audit it with any tool.
        first = next(trace.replay())
        print("\nfirst event (redacted envelope):")
        print(json.dumps(first.to_dict(), indent=2)[:400])


if __name__ == "__main__":
    main()
