"""Offline example 15 — the property suite: invariants after every step.

``oax fuzz`` (example 14) attacks a *fixed schedule*. ``oax property``
goes further: a seeded lottery picks every step of a random trace
(append, torn-tail injection, writer restart) and after *every single
step* the journal is re-read from disk and the invariants are
re-demanded — density is exactly ``0..n-1``, injected garbage isolates
as a torn tail while strict readers refuse loudly, truncation restores
the *exact pre-tear bytes*, every ``(seq, type, payload)`` round-trips,
and two independent reads fold to one replay state.

The closing property is the sharpest: rewriting every ``ts`` in the
journal to a different wall-clock folds to the *identical* replay state
and the semantic diff calls the shifted journal the same — derived state
is a function of events, never of the clock. Reports carry no timings,
so the same seed always yields the same verdict.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import read_events
from openagentx.jdiff import diff_events
from openagentx.property import render_property, run_property_trace
from openagentx.trace import replay


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-15-")

    # 1) random traces: the invariants hold after every step
    for seed in (0, 1):
        r = run_property_trace(seed=seed, n_ops=60, workdir=os.path.join(wd, f"s{seed}"))
        print(render_property(r))
        if not r["ok"]:
            raise SystemExit(f"property violations: {r['violations'][:2]}")
        if not (r["torn_injected"] > 0
                and r["torn_isolated"] == r["torn_injected"]
                and r["strict_refusals"] == r["torn_injected"]
                and r["byte_exact_resumes"] == r["torn_injected"]):
            raise SystemExit("tear cycle incomplete")
        if r["reads_checked"] != 60 or not r["dense"]:
            raise SystemExit("density was not re-checked after every step")
        if r["appends"] != r["events_written"] or r["resumes"] == 0:
            raise SystemExit("round-trip or restart broken")

    # 2) the clock property: shift every ts on disk, the fold is identical
    r = run_property_trace(seed=7, n_ops=50, workdir=os.path.join(wd, "s7"))
    events = read_events(r["journal"])
    shifted_path = os.path.join(wd, "shifted.jsonl")
    with open(shifted_path, "w", encoding="utf-8") as fh:
        for e in events:
            d = json.loads(e.to_json())
            d["ts"] = e.ts + 4242.5 + e.seq
            fh.write(json.dumps(d, sort_keys=True, ensure_ascii=False) + "\n")
    shifted = read_events(shifted_path)
    if replay(shifted) != replay(events) or not diff_events(shifted, events)["same"]:
        raise SystemExit("replay depends on the wall clock")
    print(f"ts shifted on all {len(events)} events: replay identical, "
          f"semantic diff says same")

    # 3) same seed -> identical verdict (no timings in property reports)
    a = run_property_trace(seed=9, n_ops=40, workdir=os.path.join(wd, "s9a"))
    b = run_property_trace(seed=9, n_ops=40, workdir=os.path.join(wd, "s9b"))
    a.pop("journal"), b.pop("journal")
    if a != b:
        raise SystemExit("property report not deterministic for a fixed seed")
    print(render_property(a) + "   (identical for seed 9, twice)")

    print("OK 15_property (the invariants hold after every step of a random"
          " trace: density, byte-exact tear recovery, full round-trips, and"
          " replay that never trusts the clock)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
