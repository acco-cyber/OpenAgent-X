"""Offline example 07 — fanout + structured: one task fans out to real branch
agents, then messy JSON replies get repaired and validated.

A coordinator dispatches two healthy branches and one failing branch: every
branch is a real ``AgentRunner`` run with its own journal, the parent journal
records each outcome (a ``script_error`` branch is data, not a crash), and
the coordinator answers from the fanin. On the structured side, a fenced,
trailing-comma JSON reply is repaired with honest notes and validated
against a lite schema where ``True`` is never an integer.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import sequence_dense
from openagentx.fanout import FanoutRunner
from openagentx.llm import ScriptedLLM
from openagentx.structured import parse_json_loose, validate_schema
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace

BRANCHES = {
    "deploy": ScriptedLLM([
        '{"action": {"tool": "calc", "args": {"expr": "1+2"}}, "thought": "count services"}',
        '{"reply": "deploy ok: 3 services"}',
    ], name="deploy"),
    "audit": ScriptedLLM([
        '{"action": {"tool": "echo", "args": {"text": "probe"}}, "thought": "probe then die"}',
    ], name="audit"),  # exhausts -> script_error, recorded honestly
    "db": ScriptedLLM(['{"reply": "db ok: migrations clean"}'], name="db"),
}
COORD = ScriptedLLM(['{"reply": "deploy: 3 services up; db: migrations clean"}'],
                    name="coordinator")
MESSY = '```json\n{"sum": 42, "unit": "answers",}\n```'
SCHEMA = {"type": "object", "required": ["sum"],
          "properties": {"sum": {"type": "integer"}}}


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-07-")

    # 1) fanout: three real branch runs, one honest fanin
    jp = os.path.join(wd, "journal.jsonl")
    fr = FanoutRunner(COORD, BRANCHES, builtin_tools(wd), jp, workdir=wd,
                      run_id="fanout-demo", max_steps_per_branch=6,
                      branch_tasks={n: f"run {n} checks" for n in BRANCHES})
    result = fr.run("survey deploy and database status, then summarize")
    events, _torn = load_trace(jp)
    fanin = next(e for e in events if e.type == "fanin")
    print(f"fanout: reply={result.reply!r}")
    print(f"fanout: branches={[(b.name, b.stop_reason, b.reply) for b in result.branches]}")
    print(f"fanout: fanin={fanin.payload}")

    assert result.stop_reason == "reply"
    assert result.reply == "deploy: 3 services up; db: migrations clean"
    assert [(b.name, b.stop_reason) for b in result.branches] == [
        ("deploy", "reply"), ("audit", "script_error"), ("db", "reply")]
    assert fanin.payload["replies"]["audit"] == "", "failure recorded as data"
    assert fanin.payload["stop_reasons"]["audit"] == "script_error"
    assert sequence_dense(events)
    for b in result.branches:
        bevents, _t = load_trace(b.journal_path)
        assert sequence_dense(bevents), f"branch {b.name} journal dense"
        assert bevents[0].run_id == b.run_id, "parent references the real child run"

    # 2) structured: repair + validate, hopeless input stays loud
    value, notes = parse_json_loose(MESSY)
    print(f"structured: value={value} notes={notes}")
    print(f"structured: schema_errors={validate_schema(value, SCHEMA)}")
    assert value == {"sum": 42, "unit": "answers"}
    assert notes == ["fences", "trailing_comma"]
    assert validate_schema(value, SCHEMA) == []
    assert any("got bool" in err
               for err in validate_schema({"sum": True}, SCHEMA)), \
        "True is never an integer"
    try:
        parse_json_loose("no json here at all")
        raise AssertionError("hopeless input must raise")
    except ValueError as e:
        assert str(e).startswith("unparseable JSON")
    print("OK 07_fanout_structured (real branch fanout with honest failure data,"
          " JSON repair with notes + lite schema)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
