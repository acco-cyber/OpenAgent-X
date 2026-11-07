"""Offline example 21 — replay diff: comparing two runs at the event level.

The journal is the single source of truth, so comparing two runs means
comparing their event streams. Wall-clock ``ts`` is noise between two
real runs, so the default *semantic* projection ignores it; ``strict``
mode compares every stored field. The common prefix is the longest
leading run of equal projected events; ``removed``/``added`` carry the
diverging tails with real payloads; ``same`` is true iff both tails are
empty. This example re-runs one script twice (SAME), drifts one tool
argument (DIFFERENT at the exact seq, with both payloads named), edits
a ``ts`` in a copy (semantic SAME, strict DIFFERENT), tears a tail
(isolated, prefix still SAME), and checks the CLI exit-code contract.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.cli import main as cli_main
from openagentx.jdiff import diff_journals, render_diff
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace


def _run(wd: str, name: str, script: list) -> str:
    jp = os.path.join(wd, name)
    AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp, max_steps=8,
                workdir=wd, run_id="diff-demo").run("compare my runs")
    return jp


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-21-")
    script = [
        '{"action": {"tool": "think", "args": {"note": "diff me"}}, "thought": "plan"}',
        '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
        '{"action": {"tool": "write_file", "args": {"path": "n.txt", "text": "same"}}, "thought": "persist"}',
        '{"reply": "done"}',
    ]

    # 1) two real runs of the same story: ts differs, semantics do not
    jp_a = _run(wd, "a.jsonl", script)
    jp_b = _run(wd, "b.jsonl", script)
    d = diff_journals(jp_a, jp_b)
    if not d["same"] or d["diverged_at"] != -1 or d["common"] != d["events_a"]:
        raise SystemExit(f"two identical runs must diff SAME: {d['same']}")
    if d["torn_a"] or d["torn_b"]:
        raise SystemExit("unexpected torn tails")
    print(f"re-run: SAME ({d['common']} events; wall-clock ignored by "
          "the semantic projection)")

    # 2) drift one tool argument: DIFFERENT at the exact seq, both
    #    payloads named, type counts still equal
    drifted = list(script)
    drifted[1] = drifted[1].replace("6*7", "7*7")
    jp_c = _run(wd, "c.jsonl", drifted)
    dc = diff_journals(jp_a, jp_c)
    calc_seq = next(e.seq for e in load_trace(jp_a)[0]
                    if e.type == "tool_call" and e.payload.get("tool") == "calc")
    if dc["same"] or dc["diverged_at"] != calc_seq:
        raise SystemExit(f"drift should diverge at seq {calc_seq}, "
                         f"got {dc['diverged_at']}")
    if dc["removed"][0]["payload"]["args"]["expr"] != "6*7" \
            or dc["added"][0]["payload"]["args"]["expr"] != "7*7":
        raise SystemExit("diverging tails do not carry the real payloads")
    if dc["removed_count"] != dc["added_count"] or dc["type_counts_a"] != dc["type_counts_b"]:
        raise SystemExit("drift shape is not a payload-level divergence")
    print(f"drift: DIFFERENT at seq {dc['diverged_at']} — "
          f"calc 6*7 removed, calc 7*7 added, type counts equal")

    # 3) strict mode: editing one ts in a copy is semantic-noise but
    #    strict-forensics-visible
    with open(jp_a, encoding="utf-8") as fh:
        lines = [json.loads(l) for l in fh if l.strip()]
    lines[1]["ts"] += 0.5
    jp_ts = os.path.join(wd, "ts-edited.jsonl")
    with open(jp_ts, "w", encoding="utf-8") as fh:
        for ev in lines:
            fh.write(json.dumps(ev, sort_keys=True, ensure_ascii=False) + "\n")
    d_sem = diff_journals(jp_a, jp_ts)
    d_strict = diff_journals(jp_a, jp_ts, strict=True)
    if not d_sem["same"]:
        raise SystemExit("a ts-only edit must be semantically SAME")
    if d_strict["same"]:
        raise SystemExit("strict mode must catch a ts edit")
    if d_strict["diverged_at"] != 1:
        raise SystemExit(f"strict divergence at the wrong seq: {d_strict['diverged_at']}")
    print("strict: same bytes, one edited ts -> semantic SAME, "
          f"strict DIFFERENT at seq {d_strict['diverged_at']}")

    # 4) a torn tail is isolated: the dense prefix still diffs SAME
    jp_torn = os.path.join(wd, "torn.jsonl")
    with open(jp_torn, "wb") as fh:
        fh.write(open(jp_a, "rb").read() + b'{"seq": 99, "tu')
    dt = diff_journals(jp_a, jp_torn)
    if dt["torn_b"] is not True or not dt["same"] or dt["dense_b"] is not True:
        raise SystemExit(f"torn tail not isolated: torn_b={dt['torn_b']} same={dt['same']}")
    print(f"torn: side-b garbage isolated ({dt['events_b']} prefix events), "
          "prefix verdict SAME")

    # 5) a self-diff is the identity: same=True, diverged_at=-1
    ds = diff_journals(jp_a, jp_a)
    if not ds["same"] or ds["diverged_at"] != -1:
        raise SystemExit("self-diff must be the identity")

    # 6) renders are byte-deterministic; CLI exit codes are contracts
    if render_diff(d) != render_diff(d) or "SAME" not in render_diff(d):
        raise SystemExit("render_diff is not deterministic or mislabeled")
    if "diverged at seq" not in render_diff(dc) \
            or f"seq {calc_seq}" not in render_diff(dc):
        raise SystemExit("render does not name the divergence point")
    if cli_main(["diff", jp_a, jp_b]) != 0:
        raise SystemExit("diff same must exit 0")
    if cli_main(["diff", jp_a, jp_c]) != 1:
        raise SystemExit("diff different must exit 1")
    print("cli: exit 0 = semantically same, exit 1 = different; "
          "render byte-deterministic")

    print("OK 21_replay_diff (comparing runs means comparing event streams:"
          " the semantic projection ignores wall-clock, strict mode catches"
          " a single edited ts, a drifted argument diverges at the exact seq"
          " with both real payloads named, torn tails isolate per side, and"
          " the CLI exit code is the verdict)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
