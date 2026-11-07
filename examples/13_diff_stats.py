"""Offline example 13 — journal diff + run analytics: compare runs and
fingerprint them.

Two runs of the same script should do the same things — ``oax diff`` proves
it at the event level: wall-clock ``ts`` is ignored (semantic mode), so the
two journals are SAME even though they were produced seconds apart, and
``--strict`` sees the same bytes as different because time is data there.
Tamper with one reply and the diff localizes it at exactly that seq with
both tails carried verbatim.

``oax stats`` is the numeric fingerprint of one journal: every counter is
replay()'s own (one source of truth), plus per-type event counts, per-tool
call/ok/fail pairing, and a wall-clock span that is reported but never
graded. Same file in, same text out — always.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.jdiff import diff_journals, render_diff
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.stats import render_stats, run_stats
from openagentx.tools import builtin_tools


def _run(wd: str, name: str, script: list) -> str:
    jp = os.path.join(wd, name)
    AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                max_steps=8, workdir=wd, run_id="demo-13").run("diff + stats demo")
    return jp


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-13-")
    script = [
        '{"action": {"tool": "think", "args": {"note": "compare"}}, "thought": "plan"}',
        '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
        '{"action": {"tool": "write_file", "args": {"path": "out.txt", "text": "twin"}}, "thought": "persist"}',
        '{"reply": "twins"}',
    ]

    # 1) two independent runs of one script in separate workdirs
    a = _run(wd, "a.jsonl", script)
    wd2 = tempfile.mkdtemp(prefix="oax-example-13-b-")
    b = _run(wd2, "b.jsonl", script)

    # 2) semantic diff: SAME — wall-clock ts is noise between real runs
    d = diff_journals(a, b)
    print(render_diff(d))
    if not d["same"]:
        raise SystemExit("identical scripts diffed as different")

    # 3) strict mode: every stored byte is data, and time is bytes
    ds = diff_journals(a, b, strict=True)
    if ds["same"]:
        raise SystemExit("strict mode missed the wall-clock bytes")
    print(f"strict: diverged at seq {ds['diverged_at']} (ts is data under --strict)")

    # 4) tamper with one reply — the diff localizes it with both tails
    tampered = os.path.join(wd, "tampered.jsonl")
    lines = open(a, encoding="utf-8").read().splitlines()
    reply_seq = None
    for i, ln in enumerate(lines):
        obj = json.loads(ln)
        if obj.get("type") == "reply":
            reply_seq = obj["seq"]
            obj["payload"]["text"] = "not twins"
            lines[i] = json.dumps(obj, sort_keys=True, ensure_ascii=False)
            break
    with open(tampered, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    dt = diff_journals(a, tampered)
    print(render_diff(dt))
    if dt["diverged_at"] != reply_seq:
        raise SystemExit("edit did not localize at the reply's seq")
    if dt["removed"][0]["payload"]["text"] != "twins":
        raise SystemExit("removed tail lost the original text")
    if dt["added"][0]["payload"]["text"] != "not twins":
        raise SystemExit("added tail lost the tampered text")

    # 5) stats: the fingerprint of one journal
    s = run_stats(a)
    print(render_stats(s))
    if s["tool_calls"] != 3 or s["tools"]["write_file"]["ok"] != 1:
        raise SystemExit("tool profile wrong")
    if s["type_counts"].get("tool_call") != 3:
        raise SystemExit("type counts wrong")
    again = run_stats(a)
    if render_stats(s) != render_stats(again):
        raise SystemExit("stats render not deterministic")

    print("OK 13_diff_stats (twin runs diff SAME with wall-clock ignored,"
          " strict mode sees the bytes, the tampered reply localizes,"
          " and the stats fingerprint is replay's own counters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
