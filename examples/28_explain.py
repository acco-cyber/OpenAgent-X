"""Offline example 28 — oax explain: the matrix explains itself.

Every golden task is two artifacts: a machine-readable spec
(``golden_tasks/<NN-slug>.json``) and a prose explainer (the
``### <NN-slug>`` section of ``docs/explainers.md``). ``oax explain``
joins them for one task — contract and story in one deterministic render.
This example walks the view end-to-end: a real task explained and its
fields checked against the JSON read independently, the render proven
byte-identical twice with no wall-clock, a foreign spec without prose
reported loudly instead of papered over, a missing spec raising instead
of an empty report, and the prose map cross-checked against the matrix
in both directions — the same coverage contract the verify gate and
golden task 39 enforce.
"""

import io
import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.cli import main as cli_main
from openagentx.explain import explain_task, load_explainers, render_explain


def main() -> int:
    root = os.path.join(os.path.dirname(__file__), "..")

    # 1) a real task explains: spec fields join the prose section
    first = os.path.join(root, "golden_tasks", "01-loop-stop.json")
    with open(first, encoding="utf-8") as fh:
        spec = json.load(fh)
    r = explain_task(first)
    assert r["id"] == "01-loop-stop" and r["drill"] == "loop"
    assert r["task_text"] == str(spec["task_text"])
    assert r["script_turns"] == len(spec["script"])
    assert r["expect_keys"] == sorted(spec["expect"])
    assert r["has_prose"] is True and "The run:" in r["prose"]
    print(f"explained 01-loop-stop: {r['script_turns']} turns, "
          f"expect keys {', '.join(r['expect_keys'])}")

    # 2) the render carries both halves, byte-identically, no wall-clock
    out = render_explain(r)
    assert "drill: loop" in out and str(spec["task_text"]) in out
    assert "The checks grade" in out
    assert out == render_explain(r)
    assert re.search(r"\d{10,}", out) is None
    print("render: spec + prose joined, byte-identical twice, no wall-clock")

    # 3) the path form works too
    grep_task = os.path.join(root, "golden_tasks", "37-grep-journal.json")
    g = explain_task(grep_task)
    assert g["id"] == "37-grep-journal" and g["drill"] == "grep"
    assert "cannot leak" in render_explain(g)
    print("path form: 37-grep-journal explains with its prose")

    # 4) honesty: a foreign spec without prose is reported loudly
    wd = tempfile.mkdtemp(prefix="oax-example-28-")
    ghost = os.path.join(wd, "ghost.json")
    with open(ghost, "w", encoding="utf-8") as fh:
        json.dump({"id": "99-ghost-task", "drill": "loop",
                   "task_text": "no prose for me"}, fh)
    gr = explain_task(ghost)
    gout = render_explain(gr)
    assert gr["has_prose"] is False
    assert "no prose entry for 99-ghost-task" in gout
    assert "verify gate" in gout  # the loud line, never fabricated prose
    assert gout == render_explain(gr)
    print("ghost spec: reported loudly (has_prose False), render still "
          "deterministic")

    # 5) honesty: a missing spec raises, never an empty report
    gone = os.path.join(wd, "gone.json")
    try:
        explain_task(gone)
        raise AssertionError("missing spec must raise")
    except OSError:
        pass
    print("missing spec: FileNotFoundError, not an empty report")

    # 6) coverage, both directions: every task has prose, every prose a task
    stems = sorted(f[:-5] for f in os.listdir(os.path.join(root, "golden_tasks"))
                   if f.endswith(".json"))
    prose = load_explainers(os.path.join(root, "docs", "explainers.md"))
    missing = [s for s in stems if s not in prose]
    heads = re.findall(r"^### (\d{2}-[a-z0-9-]+)", open(
        os.path.join(root, "docs", "explainers.md"), encoding="utf-8").read(),
        re.M)
    unknown = [h for h in heads if h not in set(stems)]
    assert not missing and not unknown
    print(f"coverage: {len(stems)} tasks, {len(heads)} prose entries, "
          "both directions clean")

    # 7) the CLI agrees: 0 found / 1 missing, deterministic stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc0 = cli_main(["explain", "01-loop-stop"])
        rc1 = cli_main(["explain", "no-such-task"])
    so = buf.getvalue()
    assert rc0 == 0 and rc1 == 1
    assert "explain 01-loop-stop" in so and "no task 'no-such-task'" in so
    assert re.search(r"\d{10,}", so) is None
    print("CLI: exit 0 found / 1 missing, stdout redaction-free by design")

    # 8) the matrix index: every task's prose coverage at a glance
    from openagentx.explain import explain_all, render_explain_index
    idx = explain_all()
    assert idx["ok"] is True, "the index found a task without prose"
    ids = [r["id"] for r in idx["rows"]]
    assert ids == sorted(ids), "index rows not in matrix order"
    assert len(idx["rows"]) == len(stems), "index lost a task"
    iout = render_explain_index(idx)
    assert iout == render_explain_index(idx), "index render drifted"
    assert re.search(r"\d{10,}", iout) is None, "wall-clock in index"
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc_all = cli_main(["explain", "--all"])
    assert rc_all == 0 and "explain --all" in buf.getvalue()
    print(f"index: {idx['tasks']} tasks, {idx['with_prose']} with prose, "
          "deterministic, CLI exit 0")

    print("OK 28_explain (the matrix explains itself, deterministically)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
