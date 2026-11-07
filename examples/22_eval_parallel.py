"""Offline example 22 — parallel evaluation: the clock moves, the grade doesn't.

``oax eval --workers N`` runs the golden drills on a thread pool. Because
every drill works only inside its own fresh temp workspace and reads nothing
another drill writes, the verdicts are *identical* to the serial run —
task order, per-task pass counts, and the all-green verdict included. This
example runs the full matrix both ways and proves the identity mechanically,
then reports the wall-clock difference for what it is: an observation,
never a grade.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.evaluation import run_eval

GOLDEN = os.path.join(os.path.dirname(__file__), "..", "golden_tasks")


def main() -> int:
    t0 = time.perf_counter()
    serial, ok_serial = run_eval(GOLDEN, workers=1)
    t1 = time.perf_counter()
    parallel, ok_parallel = run_eval(GOLDEN, workers=4)
    t2 = time.perf_counter()

    assert ok_serial and ok_parallel, "both modes must be all green"
    n = len(serial)
    assert len(parallel) == n, "same task count either way"
    assert n >= 36, f"the matrix only grows: {n} < 36"

    # the identity contract: verdicts are identical, per task, in order
    for s, p in zip(serial, parallel):
        assert s.task_id == p.task_id, f"order drifted at {s.task_id} vs {p.task_id}"
        assert s.drill == p.drill, f"drill mismatch on {s.task_id}"
        assert s.passed == p.passed, f"pass count drifted on {s.task_id}"
        assert len(s.checks) == len(p.checks), f"check count drifted on {s.task_id}"
        assert s.ok == p.ok, f"verdict drifted on {s.task_id}"

    # task order is the sorted path order in both modes
    ids = [r.task_id for r in serial]
    assert ids == sorted(ids), "serial report not in task order"
    assert [r.task_id for r in parallel] == ids, "parallel report not in task order"

    # every report carries its own wall-clock (reported, never graded)
    assert all(r.seconds >= 0.0 and r.checks for r in serial + parallel)

    total = sum(len(r.checks) for r in serial)
    green = sum(r.passed for r in serial)
    print(f"serial   : {n} tasks, {green}/{total} checks green "
          f"in {t1 - t0:.3f}s")
    print(f"parallel : {n} tasks, {green}/{total} checks green "
          f"(workers=4) in {t2 - t1:.3f}s")
    print("verdicts identical, task order identical, "
          f"wall-clock delta {abs((t2 - t1) - (t1 - t0)):.3f}s — "
          "an observation, never a grade")
    print("OK 22_eval_parallel (parallelism changes the clock, not the grade)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
