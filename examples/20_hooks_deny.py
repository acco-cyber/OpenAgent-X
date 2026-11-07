"""Offline example 20 — hooks deny: pre-call policy with journaled decisions.

A :class:`HookPolicy` is an ordered list of deny rules evaluated by the
runner *before* any tool executes; first matching rule wins, everything
else is allowed. Every decision is control-plane fact: the runner
journals each one as a ``hook`` event (allows included), and a denied
call never reaches the tool registry — no ``tool_call``, no
``tool_result``, zero side effects. The loop keeps going after a denial
(the agent observes ``DENY ...`` and adapts), and a denied attempt still
consumed its LLM turn, so it counts as a step. This example denies a
write, proves the file never appeared while later calls still ran, checks
every decision landed in the journal, and re-runs the whole story to a
SAME semantic diff.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.hooks import DENY, HookPolicy
from openagentx.jdiff import diff_journals
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace

SCRIPT = [
    '{"action": {"tool": "think", "args": {"note": "policy check"}}, "thought": "plan"}',
    '{"action": {"tool": "write_file", "args": {"path": "forbidden.txt", "text": "nope"}}, "thought": "try the denied tool"}',
    '{"action": {"tool": "read_file", "args": {"path": "missing.txt"}}, "thought": "adapt: read something else"}',
    '{"reply": "adapted after the denial"}',
]


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-20-")
    jp = os.path.join(wd, "journal.jsonl")
    hooks = HookPolicy([
        {"tool": "write_file", "reason": "filesystem frozen for this demo"},
    ])
    result = AgentRunner(ScriptedLLM(SCRIPT), builtin_tools(wd), jp,
                         max_steps=8, hooks=hooks, workdir=wd,
                         run_id="hooks-demo").run("respect the policy")
    events, torn = load_trace(jp)

    # 1) the run completed normally: denial is data, not a crash
    if torn or result.stop_reason != "reply":
        raise SystemExit(f"denial must not stop the run, got {result.stop_reason}")

    # 2) every decision is journaled — allows included
    hook_evts = [e for e in events if e.type == "hook"]
    decisions = [(e.payload.get("tool"), e.payload.get("decision"))
                 for e in hook_evts]
    if decisions != [("think", "allow"), ("write_file", "deny"),
                     ("read_file", "allow")]:
        raise SystemExit(f"decisions not journaled honestly: {decisions}")

    # 3) the deny decision carries its named reason
    deny = [e for e in hook_evts if e.payload.get("decision") == DENY]
    if len(deny) != 1 or deny[0].payload.get("reason") != "filesystem frozen for this demo":
        raise SystemExit(f"deny reason missing: {deny[0].payload if deny else None}")

    # 4) the denied call never reached the registry: zero side effects
    calls = [e.payload.get("tool") for e in events if e.type == "tool_call"]
    if "write_file" in calls:
        raise SystemExit("the denied write_file was journaled as a tool_call")
    if os.path.exists(os.path.join(wd, "forbidden.txt")):
        raise SystemExit("the denied write_file executed — side-effect leak")
    if not any(e.type == "tool_result" and e.payload.get("tool") == "write_file"
               for e in events):
        pass  # no tool_result for the denied call — correct
    else:
        raise SystemExit("the denied call produced a tool_result")
    print("deny: write_file refused before the registry — no tool_call, "
          "no tool_result, forbidden.txt never existed")

    # 5) the loop continued: later calls ran, and the denied attempt
    #    still consumed its LLM turn (counts as a step)
    if "think" not in calls or "read_file" not in calls:
        raise SystemExit(f"the loop did not continue after denial: {calls}")
    if result.steps != 4:
        raise SystemExit(f"denied attempt should count as a step, got {result.steps}")
    print("adapt: think + read_file ran after the denial; steps=4 (the "
          "denied turn still consumed its step)")

    # 6) policy state cannot be mutated through the snapshot
    snap = hooks.rules_snapshot()
    snap[0]["reason"] = "tampered"
    snap.append({"tool": "calc"})
    if hooks.rules_snapshot()[0]["reason"] != "filesystem frozen for this demo" \
            or len(hooks.rules_snapshot()) != 1:
        raise SystemExit("rules_snapshot leaks mutable policy state")

    # 7) first matching rule wins; a '*' rule denies everything unmatched
    wide = HookPolicy([{"tool": "calc", "reason": "no math"},
                       {"tool": "*", "reason": "locked down"}])
    if wide.decide("calc")[0] != DENY or wide.decide("read_file")[0] != DENY:
        raise SystemExit("first-match or wildcard rule did not hold")
    if wide.decide("calc")[1] != "no math":
        raise SystemExit("the wrong rule matched first")

    # 8) re-run the whole story in the same workspace (same paths, same
    #    errors): journals are event-for-event identical
    AgentRunner(ScriptedLLM(SCRIPT), builtin_tools(wd),
                os.path.join(wd, "rerun.jsonl"), max_steps=8,
                hooks=HookPolicy([{"tool": "write_file",
                                   "reason": "filesystem frozen for this demo"}]),
                workdir=wd, run_id="hooks-demo").run("respect the policy")
    d = diff_journals(jp, os.path.join(wd, "rerun.jsonl"))
    if not d["same"]:
        raise SystemExit("hooked runs are not deterministic")
    print(f"re-run: deterministic (semantic diff says SAME, {d['common']} events)")

    print("OK 20_hooks_deny (every decision is journaled as a hook event,"
          " a denied call never reaches the registry and leaves zero side"
          " effects, the loop adapts and the denied turn still counts as a"
          " step, policy state survives snapshot tampering, and first-match"
          " wildcard rules hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
