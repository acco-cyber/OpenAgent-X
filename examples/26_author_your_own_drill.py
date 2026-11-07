"""Offline example 26 — author your own drill: grade your own agent, honestly.

The eval matrix is not a museum piece; it is a workflow you can copy.
This example authors a tiny task spec from scratch (id, drill, task_text,
script, expect), grades a real offline run through the same
``run_golden_task`` path the golden matrix uses, then watches honesty
work in every direction: a deliberately wrong expectation fails loudly
by name, a drill that crashes mid-run folds into a failing
``harness_error`` check instead of a silent green, and an unknown drill
name reports ``unknown_drill`` rather than guessing. Then the spec is
repaired and goes green again. If you can read this file, you can grade
your own agents the way this repository grades itself.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.evaluation import run_golden_task


def _write(path: str, task: dict) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(task, fh)
    return path


def _red(report) -> list:
    return [f"{c.name}: {c.detail}" for c in report.checks if not c.ok]


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-26-")

    # 1) author a spec: same shape as a golden task, your own contract
    task = {
        "id": "my-first-drill",
        "title": "think, compute, answer — my own grading contract",
        "drill": "loop",
        "task_text": "think, then compute 12*11, then answer",
        "max_steps": 6,
        "script": [
            '{"action": {"tool": "think", "args": {"note": "need 12*11"}},'
            ' "thought": "planning"}',
            '{"action": {"tool": "calc", "args": {"expr": "12*11"}},'
            ' "thought": "computing"}',
            '{"reply": "12*11 = 132"}',
        ],
        "expect": {
            "stop_reason": "reply",
            "steps": 3,
            "tool_calls": 2,  # think IS a tool
            "reply": "12*11 = 132",
        },
    }
    good_path = _write(os.path.join(wd, "my-task.json"), task)

    # 2) grade it: a real run in a fresh temp workspace, real checks
    good = run_golden_task(good_path)
    assert good.ok, f"expected green, got red: {_red(good)}"
    assert good.task_id == "my-first-drill" and good.drill == "loop"
    print(f"authored drill green: {good.passed}/{len(good.checks)} checks")
    for c in good.checks:
        print(f"  PASS {c.name}" + (f" — {c.detail}" if c.detail else ""))

    # 3) honesty probe: a wrong expectation fails loudly, by name
    bad = dict(task)
    bad["id"] = "my-first-drill-wrong"
    bad["expect"] = dict(task["expect"], reply="12*11 = 144")
    wrong = run_golden_task(
        _write(os.path.join(wd, "wrong.json"), bad))
    red = [c.name for c in wrong.checks if not c.ok]
    assert not wrong.ok and red, "a wrong expectation must fail loudly"
    print(f"wrong expectation: {len(red)} check(s) red -> {red}")

    # 4) honesty probe: a drill that crashes folds into harness_error,
    #    never a silent green (a malformed script line raises mid-run)
    broken = dict(task)
    broken["id"] = "my-first-drill-broken"
    broken["script"] = ['{"action": oops not json}'] + task["script"][1:]
    folded = run_golden_task(
        _write(os.path.join(wd, "broken.json"), broken))
    names = [c.name for c in folded.checks]
    assert not folded.ok and "harness_error" in names, \
        f"expected harness_error, got {names}"
    print("crashed drill folds into harness_error:",
          next(c.detail for c in folded.checks if c.name == "harness_error"))

    # 5) honesty probe: an unknown drill name is reported, not guessed
    mystery = dict(task)
    mystery["id"] = "my-first-drill-mystery"
    mystery["drill"] = "no-such-drill"
    unknown = run_golden_task(
        _write(os.path.join(wd, "mystery.json"), mystery))
    assert not unknown.ok and unknown.checks[0].name == "unknown_drill"
    print("unknown drill reported:",
          unknown.checks[0].detail)

    # 6) repair the spec (fix the malformed line) and it goes green again
    fixed = dict(broken)
    fixed["id"] = "my-first-drill-fixed"
    fixed["script"] = list(task["script"])
    healed = run_golden_task(_write(os.path.join(wd, "fixed.json"), fixed))
    assert healed.ok, f"expected green after repair, got: {_red(healed)}"
    print(f"repaired drill green again: {healed.passed}/{len(healed.checks)}")

    print("OK 26_author_your_own_drill "
          "(grade your own agent the way this repo grades itself)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
