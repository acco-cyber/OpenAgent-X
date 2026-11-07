"""Offline example 30 — oax attest: one artifact binding every gate.

A release claim that cites five documents is a claim nobody re-checks.
``oax attest`` runs the framework's own gates against one tree — doctor
(purity + integrity), audit (0 findings), doctests (every docstring
example green), the manifest (the tree hashes identically twice) and
the matrix (every golden-task spec has its prose) — and folds them into
one verdict with two faces: a human render that carries counters only,
and a machine artifact (sort_keys JSON) that carries the root path and
the 64-hex tree hash. This example walks the attestation end-to-end: a
synthetic probe tree attests green through the same five-gate path the
real repo runs, the render is byte-identical twice with no wall-clock,
the artifact is byte-identical twice and carries the hash, a planted
credential (assembled at runtime by concatenation, never pasted) turns
the verdict red with the file named and the secret never echoed, a
crashing gate folds red carrying the real exception, and the CLI
agrees (exit 0 green / 1 red) — the same honest contract golden task 41
enforces.
"""

import io
import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.attest import artifact_json, collect_gates, render
from openagentx.cli import main as cli_main


def _mini_tree(root: str, poison: bool = False, crash: bool = False) -> str:
    """A five-gate-attestable miniature: package, task, prose, required list."""
    os.makedirs(os.path.join(root, "openagentx"))
    os.makedirs(os.path.join(root, "golden_tasks"))
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(root, "scripts"))
    with open(os.path.join(root, "openagentx", "mini.py"), "w",
              encoding="utf-8") as fh:
        fh.write('def add(a, b):\n'
                 '    """\n'
                 '    >>> add(2, 3)\n'
                 '    5\n'
                 '    """\n'
                 '    return a + b\n')
    with open(os.path.join(root, "golden_tasks", "01-mini.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"id": "01-mini", "title": "mini", "drill": "loop",
                   "task_text": "attest the mini tree", "max_steps": 3,
                   "expect": {"reply_text_matches": "mini"}}, fh)
    with open(os.path.join(root, "docs", "explainers.md"), "w",
              encoding="utf-8") as fh:
        fh.write("# explainers\n\n### 01-mini\nprose body\n")
    with open(os.path.join(root, "scripts", "required-files.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("openagentx/mini.py\n")
    if poison:
        # fixture secret assembled at runtime — never a pasted literal
        token = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
        with open(os.path.join(root, "notes.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("leak: " + token + "\n")
    if crash:
        os.remove(os.path.join(root, "scripts", "required-files.txt"))
        os.makedirs(os.path.join(root, "scripts", "required-files.txt"))
    return root


def main() -> int:
    steps: list = []

    # 1) a synthetic tree attests green through the same five-gate path
    clean = tempfile.mkdtemp(prefix="oax-attest-demo-")
    _mini_tree(clean)
    att = collect_gates(clean)
    names = [g["name"] for g in att["gates"]]
    assert att["ok"] is True, "mini tree must attest green"
    assert names == ["doctor", "audit", "doctest", "manifest", "matrix"], names
    assert all(g["ok"] for g in att["gates"]), "every gate green"
    dt_counts = att["gates"][2]["counts"]
    assert dt_counts["modules"] == 1 and dt_counts["examples"] == 1
    steps.append(f"clean tree attests green: {names}")

    # 2) the render is byte-deterministic with no wall-clock
    r1, r2 = render(att), render(att)
    assert r1 == r2, "render must be byte-identical twice"
    assert re.search(r"\d{10,}", r1) is None, "no wall-clock in the render"
    assert r1.startswith("attest: 5 gates — OK")
    steps.append("render byte-identical twice, counters only, no clock")

    # 3) the machine artifact is deterministic, sorted, carries the hash
    a1, a2 = artifact_json(att), artifact_json(att)
    assert a1 == a2, "artifact must be byte-identical twice"
    assert a1.startswith('{"gates":'), "sort_keys puts gates first"
    art = json.loads(a1)
    tree_hash = art["gates"][3]["counts"]["tree_sha256"]
    assert len(tree_hash) == 64, "the artifact carries the 64-hex tree hash"
    steps.append(f"artifact sorted + deterministic, tree {tree_hash[:12]}…")

    # 4) a planted secret turns the verdict red, file named, secret silent
    poisoned = tempfile.mkdtemp(prefix="oax-attest-demo-")
    _mini_tree(poisoned, poison=True)
    patt = collect_gates(poisoned)
    pg = patt["gates"][1]
    token = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    assert patt["ok"] is False and pg["ok"] is False, "poison must go red"
    assert "notes.txt" in pg["detail"], "the finding names the file"
    assert "github_token" in pg["detail"], "the finding names the kind"
    assert token not in pg["detail"], "the secret itself is never echoed"
    assert render(patt).startswith("attest: 5 gates — FAIL (1 red)")
    steps.append("planted secret -> FAIL (1 red), file named, secret silent")

    # 5) a gate that crashes folds red carrying the real exception
    crashy = tempfile.mkdtemp(prefix="oax-attest-demo-")
    _mini_tree(crashy, crash=True)
    catt = collect_gates(crashy)
    cg = catt["gates"][0]
    assert catt["ok"] is False and cg["ok"] is False, "crash folds red"
    assert "gate crashed: IsADirectoryError" in cg["detail"], cg["detail"]
    steps.append("crashing gate folds red: " + cg["detail"].split(": ")[1])

    # 6) the CLI agrees: exit 0 green / 1 red, stdout is the render
    import subprocess
    import sys
    r0 = subprocess.run([sys.executable, "-m", "openagentx", "attest", clean],
                        capture_output=True, text=True)
    r1c = subprocess.run([sys.executable, "-m", "openagentx", "attest",
                          poisoned],
                         capture_output=True, text=True)
    assert r0.returncode == 0 and r0.stdout.startswith("attest: 5 gates — OK")
    assert r1c.returncode == 1
    assert r1c.stdout.startswith("attest: 5 gates — FAIL (1 red)")
    steps.append("CLI exit 0 green / 1 red, stdout is the render")

    # 7) the real repository attests green too
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["attest", "."])
    assert rc == 0, "the repo itself must attest green"
    assert buf.getvalue().startswith("attest: 5 gates — OK")
    steps.append("the real repository attests green (exit 0)")

    print("attest tour:")
    for i, s in enumerate(steps, 1):
        print(f"  [{i:02d}] {s}")
    print("OK 30_attest_artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
