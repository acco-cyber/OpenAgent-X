"""Offline example 25 — oax replay --from: the fold from the middle.

Event sourcing means derived state is a deterministic fold over events.
This example folds a real run's suffix from the middle and checks the
honest contract: from 0 is the whole run, every monotone counter of the
suffix equals whole minus prefix, the non-additive fields describe only
their own window, bounds and gaps raise instead of clamping, a torn tail
is invisible and reported, and a raw token on disk never leaves the
state view — even inside last_reply.
"""

import io
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.cli import main as cli_main
from openagentx.events import Journal
from openagentx.llm import ScriptedLLM
from openagentx.replay import replay_from, render_replay
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace, replay


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-25-")
    jp = os.path.join(wd, "journal.jsonl")

    # one real run: a secret read, a think, a planned failure, a reply
    script = [
        {"thought": "read the secret",
         "action": {"tool": "vault_read", "args": {"key": "github"}}},
        {"thought": "plan the fold",
         "action": {"tool": "think", "args": {"note": "fold me from 5"}}},
        {"thought": "this one fails",
         "action": {"tool": "read_file", "args": {"path": "gone.txt"}}},
        {"reply": "replayed from the middle"},
    ]
    runner = AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                         max_steps=6)
    result = runner.run("replay-from demo")
    assert result.stop_reason == "reply"

    events, torn = load_trace(jp)
    assert not torn and len(events) == 16  # run_start + 3 tool turns + reply tail
    whole = replay(events)

    # from 0 IS the whole run — the module is a thin honest fold
    r0 = replay_from(jp, 0)
    assert r0["state"] == whole and r0["folded"] == r0["total"] == 16

    # the mid-run suffix: monotone counters add, honestly
    mid = 5  # the second action's step_start
    r_mid = replay_from(jp, mid)
    assert r_mid["folded"] == 11 and r_mid["from_seq"] == 5
    prefix = replay([ev for ev in events if ev.seq < mid])
    for k in ("runs_closed", "replies", "steps", "thoughts", "tool_calls",
              "tool_results", "tool_fails", "redactions", "errors",
              "budgets", "runs_opened"):
        assert r_mid["state"][k] == whole[k] - prefix[k], k

    # ...and the fold never claims additivity where it is false
    assert r_mid["state"]["runs_open"] == 0
    assert r_mid["state"]["last_reply"] == "replayed from the middle"
    assert r_mid["state"]["final_stop"] == "reply"

    # from the max seq folds exactly one event: the run_end alone
    r_max = replay_from(jp, events[-1].seq)
    assert r_max["folded"] == 1 and r_max["state"]["runs_closed"] == 1

    # bounds are honest: raise, never silently clamp
    for bad in (len(events) + 5, -1):
        try:
            replay_from(jp, bad)
            raise SystemExit(f"no raise for {bad}")
        except ValueError:
            pass

    # a gap is an integrity failure, not a state to fold
    gap = os.path.join(wd, "gap.jsonl")
    obj = __import__("json").loads(events[0].to_json())
    with open(gap, "w", encoding="utf-8") as fh:
        fh.write(events[0].to_json() + "\n")
        obj["seq"] = 2
        fh.write(__import__("json").dumps(obj) + "\n")
    try:
        replay_from(gap, 0)
        raise SystemExit("gap folded silently")
    except ValueError:
        pass

    # a torn tail is invisible to the fold and reported
    torn_path = os.path.join(wd, "torn.jsonl")
    with open(torn_path, "wb") as fh:
        fh.write(open(jp, "rb").read() + b'{"seq": 99, "tu')
    t = replay_from(torn_path, mid)
    assert t["torn_tail"] is True and t["state"] == r_mid["state"]

    # defense in depth: a raw token in a reply never leaves the view
    raw = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    leak = os.path.join(wd, "leak.jsonl")
    lj = Journal(leak)
    lj.start_run("leak")
    lj.append("reply", {"text": "answer carries " + raw})
    leak_r = replay_from(leak, 0)
    assert leak_r["view_redactions"] >= 1
    assert raw not in render_replay(leak_r)
    assert "[REDACTED:github_token]" in leak_r["state"]["last_reply"]

    # the render names its window and is byte-deterministic
    out = render_replay(r_mid)
    assert "from 5" in out and "of 16" in out
    assert out == render_replay(replay_from(jp, mid))
    assert not re.search(r"\d{10,}", out)  # no wall-clock anywhere

    # the CLI agrees: 0 folded / 1 missing / 2 bad bounds, stdout redacted
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert cli_main(["replay", jp, "--from", "5"]) == 0
        assert cli_main(["replay", os.path.join(wd, "gone.jsonl")]) == 1
        assert cli_main(["replay", jp, "--from", "999"]) == 2
        assert cli_main(["replay", leak]) == 0
    so = buf.getvalue()
    assert raw not in so and "[REDACTED:github_token]" in so

    # and the real drill grades green: all twelve checks
    from openagentx.evaluation import run_golden_task
    with redirect_stdout(io.StringIO()):
        report = run_golden_task(os.path.join(
            os.path.dirname(__file__), "..", "golden_tasks",
            "38-replay-from.json"))
    assert report.ok, f"replay drill red: {[c.name for c in report.checks if not c.ok]}"
    assert len(report.checks) == 12 and report.passed == 12

    print("replay --from 5: 11 of 16 events folded; 11 monotone counters "
          "add to whole-minus-prefix; runs_open/last_reply/final_stop "
          "honor their own window; bounds and gaps raise; torn tail "
          "reported; raw token redacted in the state view")
    print("drill 38-replay-from: 12/12 checks green")
    print("OK 25_replay_from (the fold from the middle, honestly)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
