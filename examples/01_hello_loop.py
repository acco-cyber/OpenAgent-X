"""Offline example 01 — hello loop: think → calc → reply, all journaled.

The smallest honest run: a scripted agent plans, computes, and answers while
every observable action lands in an append-only, dense, redacted journal.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace, text_timeline
from openagentx.events import sequence_dense


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-01-")
    script = [
        '{"action": {"tool": "think", "args": {"note": "need 6*7"}}, "thought": "planning"}',
        '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "computing"}',
        '{"reply": "6*7 = 42"}',
    ]
    result = AgentRunner(
        ScriptedLLM(script),
        builtin_tools(wd),
        os.path.join(wd, "journal.jsonl"),
        max_steps=6,
        run_id="example-01",
    ).run("compute 6*7 and answer")

    print(text_timeline(os.path.join(wd, "journal.jsonl")))
    events, _torn = load_trace(os.path.join(wd, "journal.jsonl"))
    assert result.stop_reason == "reply", result.stop_reason
    assert result.reply == "6*7 = 42"
    assert sequence_dense(events), "journal must be dense"
    assert events[-1].type == "run_end"
    print("OK 01_hello_loop (reply stop, dense journal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
