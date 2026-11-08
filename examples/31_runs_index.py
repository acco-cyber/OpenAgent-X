"""Offline example 31 — oax runs: a directory of journals, one honest table.

One journal is a run's whole truth; a directory of journals is a
portfolio. ``oax runs`` scans one directory and folds every ``*.jsonl``
journal into one deterministic table whose rows reuse the very counters
``oax stats`` prints — one grading path, so the index can never disagree
with the per-journal view. This example walks it end-to-end: synthetic
journals written as canonical ``Event`` JSON index sorted with
byte-identical renders, every row equals ``run_stats`` of that same
journal, the totals row sums exactly what the rows sum and never claims
a duration, a torn tail is flagged but still indexed, a journal torn in
the middle folds into a loud error row carrying the real exception with
no directory prefix leaked, a runtime-assembled planted secret inside a
payload never reaches the render or the artifact, an empty directory is
honest emptiness (exit 1 — truth, not failure), and the CLI agrees —
the same honest contract golden task 42 enforces.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import Event, read_events_safe
from openagentx.runs import artifact_json, index_runs, render_runs
from openagentx.stats import run_stats


def _ev(i: int, typ: str, payload: dict) -> str:
    """One canonical journal line with a fixed timestamp."""
    return Event(seq=i, run_id="tour", type=typ, payload=payload,
                 ts=1000.0 + i).to_json()


def main() -> int:
    steps: list = []
    token = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"  # assembled, never pasted
    wd = tempfile.mkdtemp(prefix="oax-runs-demo-")

    def journal(name: str, lines: list) -> str:
        path = os.path.join(wd, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path

    # 1) three journals + noise: clean, torn tail, planted payload secret
    journal("alpha.jsonl", [
        _ev(0, "run_start", {"run_id": "tour"}),
        _ev(1, "step_start", {"step": 0}),
        _ev(2, "tool_call", {"tool": "search"}),
        _ev(3, "tool_result", {"tool": "search", "ok": True}),
        _ev(4, "tool_call", {"tool": "write_file"}),
        _ev(5, "tool_result", {"tool": "write_file", "ok": False}),
    ])
    torn_line = _ev(0, "run_start", {"run_id": "tour"})[:44]
    journal("beta.jsonl", [
        _ev(0, "run_start", {"run_id": "tour"}),
        torn_line,
    ])
    journal("gamma.jsonl", [
        _ev(0, "run_start", {"run_id": "tour"}),
        _ev(1, "tool_result", {"tool": "env", "ok": True,
                               "out": "token=" + token}),
    ])
    with open(os.path.join(wd, "notes.txt"), "w", encoding="utf-8") as fh:
        fh.write("not a journal\n")

    idx = index_runs(wd)
    names = [r["name"] for r in idx["rows"]]
    assert names == ["alpha.jsonl", "beta.jsonl", "gamma.jsonl"], names
    assert idx["journals"] == 3, "notes.txt is not a journal"
    steps.append(f"3 journals indexed sorted, noise ignored: {names}")

    # 2) one grading path: every row equals run_stats of that journal
    for r in idx["rows"]:
        st = run_stats(os.path.join(wd, r["name"]))
        assert r["events"] == st["events"] and r["torn"] == st["torn_tail"]
        assert r["tool_calls"] == st["tool_calls"]
        assert r["tool_fails"] == st["tool_fails"]
    steps.append("every row's counters equal oax stats of that same journal")

    # 3) the render is byte-deterministic, counters only, no wall-clock
    r1, r2 = render_runs(idx), render_runs(idx)
    assert r1 == r2, "render must be byte-identical twice"
    assert re.search(r"\d{10,}", r1) is None, "no wall-clock in the render"
    assert "durations not summed" in r1, "additivity claimed only where true"
    assert token not in r1 and token not in artifact_json(idx), "no leak"
    steps.append("render byte-identical twice, no clock, secret never echoed")

    # 4) the totals row sums exactly what the rows sum — never a duration
    ok_rows = [r for r in idx["rows"]]
    assert idx["totals"]["events"] == sum(r["events"] for r in ok_rows) == 9
    assert idx["totals"]["tool_calls"] == 2
    assert idx["totals"]["tool_fails"] == 1
    assert "duration" not in idx["totals"]
    steps.append("totals additive where true: 9 events, durations never")

    # 5) a torn tail is a flag, not a filter — intact prefix still counts
    beta = next(r for r in idx["rows"] if r["name"] == "beta.jsonl")
    b_events, _t = read_events_safe(os.path.join(wd, "beta.jsonl"))
    assert beta["torn"] is True and beta["events"] == len(b_events) == 1
    assert idx["torn"] == 1 and "(1 torn)" in r1
    steps.append("torn tail flagged, intact prefix counted, index still ok")

    # 6) the machine artifact: byte-identical twice, sorted, path-free
    a1, a2 = artifact_json(idx), artifact_json(index_runs(wd))
    assert a1 == a2 and a1.startswith('{"events":'), "sort_keys artifact"
    assert wd not in a1, "the artifact travels — no directory path inside"
    assert json.loads(a1)["totals"]["events"] == 9
    steps.append("artifact byte-identical twice, sorted, path-free")

    # 7) a journal torn in the MIDDLE folds into a loud error row
    mid = os.path.join(wd, "mid.jsonl")
    with open(mid, "w", encoding="utf-8") as fh:
        fh.write(_ev(0, "run_start", {"run_id": "tour"}) + "\n"
                 + '{"seq": 1, "run_id": "tour", "type": "too' + "\n"
                 + _ev(2, "tool_call", {"tool": "x"}) + "\n")
    mids = index_runs(wd)
    mrow = next(r for r in mids["rows"] if r["name"] == "mid.jsonl")
    assert mids["ok"] is False, "an error row makes the index not ok"
    assert mrow["error"].startswith("TornMiddleError"), mrow["error"]
    assert wd not in mrow["error"], "no directory prefix in the render"
    assert "ERROR" in render_runs(mids)
    steps.append("middle tear folds loud: " + mrow["error"][:46])

    # 8) the CLI agrees — and honest emptiness is truth, not failure
    r0 = subprocess.run([sys.executable, "-m", "openagentx", "runs", wd],
                        capture_output=True, text=True)
    assert r0.returncode == 1, "the middle tear makes the CLI exit 1"
    assert r0.stdout.startswith("runs: 4 journals, 9 events — FAIL")
    empty = tempfile.mkdtemp(prefix="oax-runs-demo-")
    r1c = subprocess.run([sys.executable, "-m", "openagentx", "runs", empty],
                         capture_output=True, text=True)
    assert r1c.returncode == 1
    assert r1c.stdout.startswith("runs: 0 journals — nothing to index")
    steps.append("CLI exit 1 with a red row / 1 honest emptiness — never green lies")

    print("runs tour:")
    for i, s in enumerate(steps, 1):
        print(f"  [{i:02d}] {s}")
    print("OK 31_runs_index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
