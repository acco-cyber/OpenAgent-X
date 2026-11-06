"""Offline example 03 — team handoff: lead briefs, specialist computes, one journal.

The lead writes a brief file and hands off via the reserved ``handoff``
control-plane action (journaled as a ``handoff`` event, never a tool_call).
The specialist opens with the HANDOFF observation, reads the brief, computes,
and replies — all role-tagged on a single dense, redacted journal.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import sequence_dense
from openagentx.llm import ScriptedLLM
from openagentx.team import TeamRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace, text_timeline


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-03-")
    lead = ScriptedLLM([
        '{"action": {"tool": "write_file", "args": {"path": "brief.txt", '
        '"text": "brief: compute 6*7"}}, "thought": "write the brief first"}',
        '{"action": {"tool": "handoff", "args": {"to": "specialist", '
        '"reason": "math delegated"}}, "thought": "delegate the computation"}',
    ], name="lead")
    specialist = ScriptedLLM([
        '{"action": {"tool": "read_file", "args": {"path": "brief.txt"}}, '
        '"thought": "consume the brief"}',
        '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "computing"}',
        '{"reply": "6*7 = 42"}',
    ], name="specialist")
    jp = os.path.join(wd, "journal.jsonl")
    result = TeamRunner(lead, specialist, builtin_tools(wd), jp,
                        max_steps_per_role=6, workdir=wd,
                        run_id="example-03").run("compute 6*7 as a team")

    events, _torn = load_trace(jp)
    print(text_timeline(jp))

    handoffs = [e for e in events if e.type == "handoff"]
    roles = [e.payload.get("role") for e in events if e.type == "role_start"]
    replies = [e for e in events if e.type == "reply"]
    brief = open(os.path.join(wd, "brief.txt"), encoding="utf-8").read()

    assert result.stop_reason == "reply", result.stop_reason
    assert result.handoffs == 1 and len(handoffs) == 1
    assert handoffs[0].payload.get("from_role") == "lead"
    assert handoffs[0].payload.get("to_role") == "specialist"
    assert handoffs[0].payload.get("reason") == "math delegated"
    assert roles == ["lead", "specialist"], roles
    assert "brief: compute 6*7" in brief, "lead's brief must reach disk"
    assert replies and replies[0].payload.get("role") == "specialist"
    assert replies[0].seq > handoffs[0].seq, "reply must come after the handoff"
    assert result.reply == "6*7 = 42"
    assert len({e.run_id for e in events}) == 1, "one journal, one run identity"
    assert sequence_dense(events) and events[-1].type == "run_end"
    reopened, _t2 = load_trace(jp)
    assert sequence_dense(reopened), "journal must reopen dense"
    print("OK 03_team_handoff (lead->specialist handoff, shared dense journal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
