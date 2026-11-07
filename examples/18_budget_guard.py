"""Offline example 18 — budget guard: the tool-call governor up close.

``max_tool_calls`` stops the loop *before* the rejected call: the
``budget`` event names the tool that was refused and carries
``used``/``cap``, the cap is recorded at ``run_start``, every executed
call precedes the budget line, the rejected call leaves zero side
effects, the capped attempt still counts as a step, and no reply is
fabricated. Budget exhaustion is a different animal from script
exhaustion and from ``max_steps`` — this example proves all three are
distinct stop reasons, then re-runs the capped run and diffs the two
journals event-for-event.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.jdiff import diff_journals
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace

SCRIPT = [
    '{"action": {"tool": "think", "args": {"note": "guard me"}}, "thought": "plan"}',
    '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
    '{"action": {"tool": "write_file", "args": {"path": "note.txt", "text": "allowed"}}, "thought": "persist"}',
    '{"action": {"tool": "write_file", "args": {"path": "note2.txt", "text": "rejected"}}, "thought": "over the cap"}',
    '{"reply": "never reached"}',
]


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-18-")
    jp = os.path.join(wd, "journal.jsonl")
    llm = ScriptedLLM(SCRIPT)
    runner = AgentRunner(llm, builtin_tools(wd), jp, max_steps=8,
                         max_tool_calls=3, workdir=wd,
                         run_id="budget-demo")
    result = runner.run("guard my tool calls")
    events, torn = load_trace(jp)

    # 1) the stop is a budget stop, carried by the final run_end
    if torn or result.stop_reason != "budget":
        raise SystemExit(f"expected budget stop, got {result.stop_reason}")
    if events[-1].type != "run_end" or events[-1].payload.get("stop_reason") != "budget":
        raise SystemExit("run_end does not carry the budget stop")
    if events[-1].payload.get("cap") != 3:
        raise SystemExit("run_end does not record the cap")

    # 2) the budget event names the rejected tool and carries used/cap
    budget = [e for e in events if e.type == "budget"]
    if len(budget) != 1:
        raise SystemExit(f"expected exactly one budget event, got {len(budget)}")
    b = budget[0].payload
    if b.get("kind") != "tool_calls" or b.get("used") != 3 or b.get("cap") != 3:
        raise SystemExit(f"budget payload is not honest: {b}")
    if b.get("rejected_tool") != "write_file":
        raise SystemExit(f"budget named the wrong tool: {b}")

    # 3) the cap was recorded at run_start, before anything ran
    start = events[0]
    if start.type != "run_start" or start.payload.get("max_tool_calls") != 3:
        raise SystemExit("run_start does not record the cap")

    # 4) executed calls all precede the budget line
    calls = [e for e in events if e.type == "tool_call"]
    if len(calls) != 3 or any(e.seq > budget[0].seq for e in calls):
        raise SystemExit("executed calls are not exactly the pre-budget prefix")
    if not all(e.seq < budget[0].seq for e in events if e.type == "tool_result"):
        raise SystemExit("a tool_result landed after the budget line")

    # 5) side effects: the allowed write happened, the rejected one never did
    if not os.path.exists(os.path.join(wd, "note.txt")):
        raise SystemExit("the allowed write_file did not execute")
    if os.path.exists(os.path.join(wd, "note2.txt")):
        raise SystemExit("the REJECTED write_file executed — side-effect leak")

    # 6) no reply fabricated; the capped attempt still counts as a step
    if result.reply != "" or any(e.type == "reply" for e in events):
        raise SystemExit("a reply was fabricated after the budget stop")
    if result.steps != 4:
        raise SystemExit(f"capped attempt should count as a step, got {result.steps}")

    # 7) the scripted tail stays unconsumed: budget != script exhaustion
    if llm.cursor != 4 or llm.cursor >= len(SCRIPT):
        raise SystemExit(f"script cursor wrong: {llm.cursor}/{len(SCRIPT)}")

    print("budget: stop=budget used=3/3 rejected=write_file steps=4 "
          "tail-unconsumed side-effects-clean")

    # 8) script exhaustion != max_steps: two control runs
    wd2 = tempfile.mkdtemp(prefix="oax-example-18b-")
    r_reply = AgentRunner(ScriptedLLM(['{"reply": "done"}']),
                          builtin_tools(wd2), os.path.join(wd2, "j.jsonl"),
                          max_steps=8, workdir=wd2, run_id="short").run("t")
    if r_reply.stop_reason != "reply" or r_reply.steps != 1:
        raise SystemExit("a one-turn script must end as reply, not max_steps")
    llm3 = ScriptedLLM([
        '{"action": {"tool": "think", "args": {"note": "x"}}, "thought": "t"}',
        '{"reply": "never reached"}',
    ])
    r_steps = AgentRunner(llm3, builtin_tools(wd2), os.path.join(wd2, "k.jsonl"),
                          max_steps=1, workdir=wd2, run_id="capped").run("t")
    if r_steps.stop_reason != "max_steps" or r_steps.steps != 1:
        raise SystemExit("max_steps stop expected")
    if llm3.cursor >= 2:
        raise SystemExit("max_steps run consumed the whole script")
    print("stop taxonomy: reply / max_steps / budget are three different animals")

    # 9) re-run the capped story: journals are event-for-event identical
    wd3 = tempfile.mkdtemp(prefix="oax-example-18c-")
    AgentRunner(ScriptedLLM(SCRIPT), builtin_tools(wd3),
                os.path.join(wd3, "journal.jsonl"), max_steps=8,
                max_tool_calls=3, workdir=wd3, run_id="budget-demo"
                ).run("guard my tool calls")
    d = diff_journals(jp, os.path.join(wd3, "journal.jsonl"))
    if not d["same"] or d["diverged_at"] != -1:
        raise SystemExit("two capped runs are not semantically identical")
    print("re-run: deterministic (semantic diff says SAME, "
          f"{d['common']} common events)")

    print("OK 18_budget_guard (the governor stops BEFORE the rejected call:"
          " the budget event names the refused tool, the cap is recorded at"
          " run_start, the rejected call leaves zero side effects, the"
          " capped attempt counts as a step, and budget is not script"
          " exhaustion and not max_steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
