"""Offline example 09 — planner + snapshot travel: plan with one turn,
execute every step with a real sub-agent, then walk the journal's history.

A ``PlannerExecutor`` asks the planner for a JSON plan (the reply is fenced
JSON with a trailing comma — repaired with notes), executes each step with a
real ``AgentRunner`` on its own journal, and records a failing step as data
instead of crashing. ``snapshot_at``/``travel`` then walk the parent
journal: the state at any checkpoint is a pure prefix fold, so appending
events later never rewrites history.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import read_events_safe
from openagentx.llm import ScriptedLLM
from openagentx.planner import PlannerExecutor
from openagentx.snapshot import monotone, snapshot_at, travel
from openagentx.tools import builtin_tools
from openagentx.trace import replay


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-09-")
    jp = os.path.join(wd, "journal.jsonl")

    planner = ScriptedLLM([
        # fenced JSON + trailing comma: parse_json_loose repairs with notes
        '{"reply": "```json\\n{\\"steps\\": [\\"write the plan file\\", '
        '\\"echo the version\\", \\"read it back\\"],}\\n```"}',
        '{"reply": "release prep: 3 of 3 steps ok"}',
    ])
    step_llms = [
        ScriptedLLM([
            '{"action": {"tool": "write_file", "args": {"path": "release.txt", '
            '"text": "launching 2027"}}, "thought": "persist"}',
            '{"reply": "file written"}',
        ]),
        ScriptedLLM([
            '{"action": {"tool": "echo", "args": {"text": "v2.0-rc1"}}, '
            '"thought": "announce"}',
            '{"reply": "version announced"}',
        ]),
        ScriptedLLM(['{"reply": "content verified"}']),
    ]

    r = PlannerExecutor(planner, step_llms, builtin_tools(wd), jp, workdir=wd,
                        run_id="plan-demo").run("prep the release")
    print(f"planner: plan={r.plan}")
    print(f"planner: steps={[(s.index, s.stop_reason) for s in r.steps]}")
    print(f"planner: reply={r.reply!r}")
    assert r.stop_reason == "reply"
    assert r.plan == ["write the plan file", "echo the version",
                      "read it back"]
    assert [s.stop_reason for s in r.steps] == ["reply", "reply", "reply"]
    assert r.reply == "release prep: 3 of 3 steps ok"

    events, torn = read_events_safe(jp)
    assert not torn
    plan_ev = [e for e in events if e.type == "plan"][0]
    print(f"journal: plan notes={plan_ev.payload['notes']}")
    assert plan_ev.payload["notes"] == ["fences", "trailing_comma"]
    child = os.path.join(wd, [e for e in events
                              if e.type == "step_start"][0].payload["journal"])
    cevents, _ct = read_events_safe(child)
    assert cevents[0].run_id == "plan-demo-s00"  # parent references children
    print(f"journal: child run_id={cevents[0].run_id}, dense="
          f"{[e.seq for e in cevents] == list(range(len(cevents)))}")

    # ---- time travel over the parent journal ------------------------------
    end = events[-1].seq
    states = travel(events, [0, 4, 8, end])
    for s in states:
        st = s["state"]
        print(f"travel: seq={s['seq']:2d} steps={st['steps']} "
              f"tool_calls={st['tool_calls']} replies={st['replies']}")
    assert states[0]["state"]["steps"] == 0          # zero state at seq 0
    assert monotone(states)                          # counters never decrease
    assert states[-1]["state"] == replay(events)     # final == full fold
    assert states[-1]["state"]["last_reply"] == r.reply

    # prefix purity: a later checkpoint cannot be rewritten by new events
    before = snapshot_at(events, 4)
    later = snapshot_at(events, end)
    assert before["state"]["replies"] == 0 < later["state"]["replies"]
    assert before == snapshot_at(events[:5], 4)      # fold of the prefix only
    print("travel: prefix at seq 4 unchanged by everything after it")

    # determinism: fixed run_id re-run folds to an identical stream
    wd2 = os.path.join(wd, "rerun")
    os.makedirs(wd2)
    r2 = PlannerExecutor(
        ScriptedLLM([s for s in planner.script]),
        [ScriptedLLM([s for s in x.script]) for x in step_llms],
        builtin_tools(wd2), os.path.join(wd2, "journal.jsonl"),
        workdir=wd2, run_id="plan-demo").run("prep the release")
    ev2, _t2 = read_events_safe(os.path.join(wd2, "journal.jsonl"))
    fp = lambda evs: [(e.seq, e.run_id, e.type,
                       json.dumps(e.payload, sort_keys=True)) for e in evs]
    assert fp(events) == fp(ev2) and r2.reply == r.reply
    print("rerun: structurally identical journal")

    print("OK 09_planner_snapshot (plan -> execute -> summarize,"
          " checkpoints are pure prefix folds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
