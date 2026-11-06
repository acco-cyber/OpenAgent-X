"""Offline example 02 — the redaction boundary: tools run on truth, journals don't.

A scripted agent reads a fixture credential from the vault. The tool executes
on the real value, but the journal stores only ``[REDACTED:github_token]`` —
proof that observation never leaks secrets while execution keeps them. A plain
``think`` note shows ordinary prose passes through untouched.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import sequence_dense
from openagentx.llm import ScriptedLLM
from openagentx.redact import REDACTED_PREFIX
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools, vault_value
from openagentx.trace import load_trace, text_timeline


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-02-")
    token = vault_value("github")  # runtime-concatenated fixture, never a real secret
    plain_note = "token handled at the boundary, nothing to hide here"
    script = [
        '{"action": {"tool": "vault_read", "args": {"key": "github"}}, '
        '"thought": "fetch the fixture token"}',
        '{"action": {"tool": "think", "args": {"note": "' + plain_note + '"}}, '
        '"thought": "reasoning is not a secret"}',
        '{"reply": "token stored safely"}',
    ]
    jp = os.path.join(wd, "journal.jsonl")
    result = AgentRunner(
        ScriptedLLM(script), builtin_tools(wd), jp,
        max_steps=6, run_id="example-02",
    ).run("read the github token and confirm safe handling")

    events, _torn = load_trace(jp)
    raw = open(jp, encoding="utf-8").read()
    print(text_timeline(jp))

    assert result.stop_reason == "reply", result.stop_reason
    assert token not in raw, "raw token must never reach the journal"
    assert f"{REDACTED_PREFIX}github_token]" in raw, "redaction marker must be journaled"
    assert any(int((e.payload or {}).get("redactions", 0) or 0) >= 1
               for e in events if e.type == "tool_result"), "redaction count must be recorded"
    assert any(e.type == "tool_call"
               and (e.payload.get("args") or {}).get("note") == plain_note
               for e in events), "plain prose must survive without false positives"
    assert sequence_dense(events) and events[-1].type == "run_end"
    print("OK 02_redaction_demo (boundary redaction, no false positives, dense journal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
