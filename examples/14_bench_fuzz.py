"""Offline example 14 — bench + fuzz: measure the journal, then attack it.

``oax bench`` drives a deterministic synthetic workload through a real
Journal and reports append / read-back / replay rates as honest single-run
wall-clock — the numbers are observations, the structure is the contract
(every planned event lands dense, bytes match the plan, doubling the
workload doubles the journal, and the zero-event bench reports 0.0 rates
instead of dividing by zero).

``oax fuzz`` then attacks the journal contract with a seeded schedule:
garbage appended at the tail every 7th op must isolate and truncate
cleanly, an undecodable line spliced before the tail every 11th op must
raise loudly and restore byte-identically, and every unicode/nested
payload must round-trip with two reads folding to one replay state. No
timings in the fuzz report — the same seed always yields the same verdict.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.bench import render_bench, run_bench
from openagentx.fuzz import render_fuzz, run_fuzz, run_fuzz_suite


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-14-")

    # 1) bench: deterministic workload, honest wall-clock
    small = run_bench(events=400, workdir=os.path.join(wd, "small"))
    big = run_bench(events=800, workdir=os.path.join(wd, "big"))
    print(render_bench(small))
    if small["events"] != 400 or not small["dense"]:
        raise SystemExit("bench lost events")
    if big["events"] != 800 or big["journal_bytes"] <= small["journal_bytes"]:
        raise SystemExit("bench scale broken")
    zero = run_bench(events=0, workdir=os.path.join(wd, "zero"))
    if zero["events"] != 0 or zero["append_eps"] != 0.0 or zero["journal_bytes"] != 0:
        raise SystemExit("zero bench not honest")

    # 2) fuzz: seeded attacks on the journal contract
    for r in run_fuzz_suite(seeds=(0, 1), n_ops=70, workdir=os.path.join(wd, "fuzz")):
        print(render_fuzz(r))
        if not r["ok"]:
            raise SystemExit(f"fuzz violations: {r['violations'][:2]}")
        exp_torn = len([i for i in range(70) if i % 7 == 3])
        exp_mid = len([i for i in range(70) if i % 11 == 5])
        if r["torn_injected"] != exp_torn or r["middle_tears"] != exp_mid:
            raise SystemExit("attack schedule did not fire exactly")

    # 3) same seed -> byte-identical verdict (no timings in fuzz reports)
    a = run_fuzz(seed=9, n_ops=35, workdir=os.path.join(wd, "s9a"))
    b = run_fuzz(seed=9, n_ops=35, workdir=os.path.join(wd, "s9b"))
    a.pop("journal"), b.pop("journal")
    if a != b:
        raise SystemExit("fuzz report not deterministic for a fixed seed")
    print(render_fuzz(a) + "   (identical for seed 9, twice)")

    print("OK 14_bench_fuzz (bench structure is the contract and timings are"
          " observations; the seeded attack schedule fires exactly and the"
          " journal contract holds under every injection)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
