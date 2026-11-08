"""Offline example 35 — oax eval --list / --only: the matrix is addressable.

The golden matrix grew to 46 drills, and running all of them every time
you touch one drill is the tax that stops you iterating. So the matrix
became addressable: ``oax eval --list`` prints the honest inventory (id
+ drill rows in task order, the count named, exit 1 on emptiness) and
``oax eval --only <names>`` runs a named subset — every name matches a
task id exactly (``45-species``) or a drill name (``species``, which
selects *every* task carrying that drill), duplicates dedupe, ``--list``
composes with ``--only``, and unknown or blank names are rejected loudly
before anything runs: a subset you can't name is not a subset, and
silently running the rest would bless the typo. Underneath, the timed
core is factored into ``run_selected`` so a subset run grades through
the same path as the full run — the subset's checks are the full run's
checks. This example walks the surface the way golden task 46 grades
it: the inventory, the composition, single and two-drill subsets in
task order, id/drill resolution, deduping, the loud rejections, a
poisoned temp matrix whose red task is named with its failing check,
the one-grading-path proof, and the honest emptiness of an empty dir.
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.evaluation import (list_golden_tasks, resolve_only,
                                   run_golden_task, run_selected)


def main() -> int:
    steps: list = []
    root = os.path.join(os.path.dirname(__file__), "..")

    def cli(*argv: str):
        return subprocess.run([sys.executable, "-m", "openagentx", *argv],
                              capture_output=True, text=True, cwd=root)

    # 1) --list: the honest inventory
    l1 = cli("eval", "--list")
    rows = [ln for ln in l1.stdout.splitlines() if ln and not ln.startswith("eval")]
    steps.append(f"--list: exit {l1.returncode}, {len(rows)} rows sorted, "
                 f"'{l1.stdout.strip().splitlines()[-1]}'")

    # 2) --list composes with --only
    l2 = cli("eval", "--only", "species", "--list")
    rows2 = [ln for ln in l2.stdout.splitlines() if ln and not ln.startswith("eval")]
    steps.append(f"--only species --list: {len(rows2)} row -> '{rows2[0]}'")

    # 3) a named subset runs exactly its reports, green
    s1 = cli("eval", "--only", "species")
    steps.append(f"--only species: exit {s1.returncode}, "
                 f"'{s1.stdout.strip().splitlines()[-1][:74]}'")

    # 4) two drill names run two reports in task order
    s2 = cli("eval", "--only", "species,chain")
    order = [ln.split()[0] for ln in s2.stdout.splitlines()
             if ln and not ln.startswith("eval:")]
    steps.append(f"--only species,chain: exit {s2.returncode}, order {' -> '.join(order)}")

    # 5) a task id and its drill name resolve to the same task
    #    (timings are reported, never graded — normalize the seconds column)
    import re

    def timed(out: str) -> list:
        return [re.sub(r"\d+\.\d{3}s", "N.NNNs", ln)
                for ln in out.splitlines() if ln and not ln.startswith("eval:")]

    same = (timed(cli("eval", "--only", "45-species").stdout)
            == timed(cli("eval", "--only", "species").stdout))
    steps.append(f"id (45-species) == drill name (species): {same}")

    # 6) duplicates dedupe
    sel, unk = resolve_only(list_golden_tasks(os.path.join(root, "golden_tasks")),
                            ["species", "species", "45-species"])
    steps.append(f"dedupe: three names -> {len(sel)} task, unknown={unk}")

    # 7-8) unknown and blank names rejected before anything runs
    u1 = cli("eval", "--only", "ghost")
    steps.append(f"unknown 'ghost': exit {u1.returncode}, "
                 f"'{u1.stdout.strip()[:64]}', task lines: "
                 f"{sum(1 for ln in u1.stdout.splitlines() if ln and not ln.startswith('eval'))}")
    u2 = cli("eval", "--only", "species,")
    steps.append(f"blank name: exit {u2.returncode}, '{u2.stdout.strip()[:64]}'")

    # 9) a poisoned temp matrix: the red task named, nothing blessed
    wd = tempfile.mkdtemp(prefix="oax-eval-demo-")
    with open(os.path.join(wd, "01-green.json"), "w", encoding="utf-8") as fh:
        json.dump({"id": "green-audit", "drill": "audit"}, fh)
    with open(os.path.join(wd, "02-red.json"), "w", encoding="utf-8") as fh:
        json.dump({"id": "red-ghost", "drill": "ghost"}, fh)
    r1 = cli("eval", wd, "--only", "red-ghost")
    fail_line = next((ln.strip() for ln in r1.stdout.splitlines()
                      if ln.strip().startswith("FAIL")), "")
    steps.append(f"poisoned matrix --only red-ghost: exit {r1.returncode}, '{fail_line[:58]}'")
    r2 = cli("eval", wd, "--only", "green-audit,red-ghost")
    mixed = [ln.split()[0] for ln in r2.stdout.splitlines()
             if ln and not ln.startswith("eval:") and not ln.strip().startswith("FAIL")]
    steps.append(f"mixed subset: exit {r2.returncode}, reports {' -> '.join(mixed)}")

    # 10) one grading path: the subset IS the full run's slice
    sel2, _ = resolve_only(list_golden_tasks(os.path.join(root, "golden_tasks")),
                           ["species"])
    sub, ok = run_selected(sel2)
    direct = run_golden_task(sel2[0])
    steps.append(f"one grading path: subset ok={ok}, "
                 f"checks identical={[c.name for c in sub[0].checks] == [c.name for c in direct.checks]}")

    # 11) an empty dir is honest emptiness
    empty = tempfile.mkdtemp(prefix="oax-eval-empty-")
    le = cli("eval", empty, "--list")
    steps.append(f"empty dir --list: exit {le.returncode}, '{le.stdout.strip()[:56]}'")

    for i, s in enumerate(steps, 1):
        print(f"  [{i:02d}] {s}")
    print("OK 35_eval_only_tour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
