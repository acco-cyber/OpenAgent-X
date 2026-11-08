"""Offline example 32 — oax doctor: the auditor audits itself.

The doctor is the gate everything else runs behind: six checks that
refuse third-party imports, network modules, a drifted manifest and
broken golden-task contracts before any drill executes. But an
auditor's verdict is only worth what its failure edges catch — so this
example grades the gates themselves, exactly the way golden task 43
does: the real tree reports 6/6 with a byte-deterministic render (no
wall-clock), a clean synthetic workspace is green too (purity is the
absence of offenders, not the presence of this repo), a planted
third-party import is caught with ``file:module`` named (the probe is
parsed, never executed), a planted network import the same way, a
missing required file is named, a truncated spec folds into its gate
carrying the real exception without crashing the doctor, an unknown
drill name is named, the gates are proven independent (one poisoned
tree turns exactly the planted gates red, never more), and the CLI
agrees — 0 green with the verdict in stdout, 1 red naming its failing
gates. Every probe lives in a fresh temp workspace.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.doctor import render_doctor, run_doctor


def main() -> int:
    steps: list = []
    wd = tempfile.mkdtemp(prefix="oax-doctor-demo-")

    def gate(checks: list, name: str):
        return [c for c in checks if c[0] == name][0]

    # 1) the real tree: 6/6, render byte-identical twice, no wall-clock
    real = run_doctor(".")
    assert len(real) == 6 and all(ok for _, ok, _ in real), real
    r1, r2 = render_doctor(real), render_doctor(real)
    assert r1 == r2, "the verdict must render byte-identically"
    assert re.search(r"\d{10,}", r1) is None, "no wall-clock in the verdict"
    assert r1.splitlines()[-1] == "doctor: OK (6/6)"
    steps.append("real tree 6/6, verdict byte-identical twice, no wall-clock")

    # 2) a clean synthetic workspace is green too
    os.makedirs(os.path.join(wd, "openagentx"))
    os.makedirs(os.path.join(wd, "scripts"))
    os.makedirs(os.path.join(wd, "golden_tasks"))
    with open(os.path.join(wd, "scripts", "required-files.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("scripts/required-files.txt\n")
    with open(os.path.join(wd, "golden_tasks", "01-clean.json"), "w",
              encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "01-clean", "title": "shape probe",
                             "drill": "loop"}))
    clean = run_doctor(wd)
    assert len(clean) == 6 and all(ok for _, ok, _ in clean), clean
    steps.append("a clean synthetic workspace passes 6/6 as well")

    # 3) a planted third-party import is caught, file:module named
    #    (the probe is parsed by the doctor, never executed)
    with open(os.path.join(wd, "openagentx", "foreign.py"), "w",
              encoding="utf-8") as fh:
        fh.write("import numpy  # probe: parsed only, never executed\n")
    std = gate(run_doctor(wd), "stdlib_purity")
    assert std[1] is False and "foreign.py:numpy" in std[2], std
    steps.append(f"planted numpy import caught: {std[0]} FAIL {std[2]}")

    # 4) a planted network import is caught the same way
    with open(os.path.join(wd, "openagentx", "netty.py"), "w",
              encoding="utf-8") as fh:
        fh.write("import socket  # probe\n")
    off = gate(run_doctor(wd), "offline_purity")
    assert off[1] is False and "netty.py:socket" in off[2], off
    steps.append(f"planted socket import caught: {off[0]} FAIL {off[2]}")

    # 5) a missing required file is named
    with open(os.path.join(wd, "scripts", "required-files.txt"), "a",
              encoding="utf-8") as fh:
        fh.write("gone.txt\n")
    req = gate(run_doctor(wd), "required_files")
    assert req[1] is False and "gone.txt" in req[2], req
    steps.append(f"missing required file named: {req[0]} FAIL {req[2]}")

    # 6) a truncated spec folds into its gate — reported, never a crash
    with open(os.path.join(wd, "golden_tasks", "bad.json"), "w",
              encoding="utf-8") as fh:
        fh.write('{"id": "broken", "drill": ')
    bad = run_doctor(wd)
    assert len(bad) == 6, "the doctor reports six gates even on a red tree"
    gt = gate(bad, "golden_tasks_valid")
    assert gt[1] is False and "bad.json" in gt[2], gt
    steps.append("truncated spec folded into the gate with the real exception")

    # 7) an unknown drill name fails the same gate, file named
    with open(os.path.join(wd, "golden_tasks", "ghost.json"), "w",
              encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "99-ghost", "title": "ghost",
                             "drill": "no_such_drill"}))
    gt2 = gate(run_doctor(wd), "golden_tasks_valid")
    assert gt2[1] is False and "ghost.json" in gt2[2], gt2
    steps.append("unknown drill name named by golden_tasks_valid")

    # 8) the gates are independent: exactly the planted gates are red
    final = run_doctor(wd)
    red = sorted(n for n, ok, _ in final if not ok)
    assert red == ["golden_tasks_valid", "offline_purity", "required_files",
                   "stdlib_purity"], red
    assert gate(final, "python>=3.10")[1] and gate(
        final, "workspace_writable")[1]
    steps.append(f"gates independent: exactly 4 red — {', '.join(red)}")

    # 9) the CLI agrees: 0 green with the verdict in stdout, 1 red loud
    c0 = subprocess.run([sys.executable, "-m", "openagentx", "doctor", "."],
                        capture_output=True, text=True)
    assert c0.returncode == 0 and "doctor: OK (6/6)" in c0.stdout
    c1 = subprocess.run([sys.executable, "-m", "openagentx", "doctor", wd],
                        capture_output=True, text=True)
    assert c1.returncode == 1 and "doctor: FAIL" in c1.stdout
    assert "FAIL" in c1.stdout and "stdlib_purity" in c1.stdout
    steps.append("CLI 0 green / 1 red with the failing gates named")

    print("doctor gates tour:")
    for i, s in enumerate(steps, 1):
        print(f"  [{i:02d}] {s}")
    print("OK 32_doctor_gates_tour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
