"""Seeded fuzz harness — random traces, deterministic verdicts.

A seeded ``random.Random`` generates event payloads (unicode, nesting,
random sizes) and drives a real ``Journal`` through the hardest cycles the
journal contract promises to survive:

- **torn tails**: garbage bytes are appended mid-run; the lenient reader
  must isolate the tail with the prefix intact, the truncation helper must
  remove exactly the garbage, and appending must continue with a dense
  sequence;
- **middle tears**: an undecodable line is spliced *before* the tail; the
  strict reader must raise (integrity failure is never silently skipped);
- **round-trip**: every generated ``(seq, type, payload)`` must come back
  byte-for-byte equal from disk, unicode and all;
- **replay determinism**: two independent read-backs fold to identical
  derived state.

Determinism contract: the schedule is fixed by ``seed`` and ``n_ops`` (torn
tails at ops where ``i % 7 == 3``, middle tears where ``i % 11 == 5``), the
report carries no timings, so the same seed always yields the same report.
"""

from __future__ import annotations

import os
import random
import tempfile

from .events import (Journal, TornMiddleError, read_events,
                     read_events_safe, sequence_dense)
from .trace import replay, truncate_torn_tail

TYPES = ("run_start", "step_start", "thought", "tool_call", "tool_result",
         "reply", "error", "budget", "note", "run_end")
ALPHABET = ("abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_{}\"'\\éπ漢字")
TOOLS = ("calc", "write_file", "read_file", "think")


def _rand_str(rng: random.Random) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(rng.randrange(1, 24)))


def _rand_payload(rng: random.Random) -> dict:
    kind = rng.randrange(5)
    if kind == 0:
        return {"note": _rand_str(rng)}
    if kind == 1:
        return {"tool": rng.choice(TOOLS), "args": {"x": rng.randrange(1000)}}
    if kind == 2:
        return {"ok": rng.random() < 0.5,
                "result": {"n": rng.randrange(100), "text": _rand_str(rng)}}
    if kind == 3:
        return {"nested": {"deep": {"list": [_rand_str(rng)
                                             for _ in range(rng.randrange(4))]}}}
    return {"expr": f"{rng.randrange(99)}*{rng.randrange(99)}",
            "value": rng.random()}


class _Fuzz:
    """Mutable accumulator for one fuzz run (violations + check counter)."""

    def __init__(self, seed: int):
        self.seed = seed
        self.violations: list = []
        self.checks = 0
        self.torn_injected = 0
        self.middle_tears = 0

    def check(self, ok: bool, what: str) -> None:
        self.checks += 1
        if not ok:
            self.violations.append(what)


def _torn_tail_cycle(fz: _Fuzz, path: str, expected: int) -> None:
    """Append garbage bytes; isolation + truncation + dense resume."""
    with open(path, "ab") as fh:
        fh.write(b'{"seq": 999, "typ')
    back, torn = read_events_safe(path)
    fz.check(torn and len(back) == expected,
             f"seed {fz.seed}: torn tail not isolated at {expected}")
    fz.torn_injected += 1
    fz.check(truncate_torn_tail(path),
             f"seed {fz.seed}: truncation removed nothing")
    back2, torn2 = read_events_safe(path)
    fz.check(not torn2 and len(back2) == expected and sequence_dense(back2),
             f"seed {fz.seed}: prefix not clean after truncation")


def _middle_tear_cycle(fz: _Fuzz, path: str, rng: random.Random) -> None:
    """Splice an undecodable line before the tail; strict read must raise."""
    data = open(path, "rb").read()
    lines = data.splitlines(keepends=True)
    if len(lines) < 2:
        return
    lines.insert(rng.randrange(1, len(lines)), b'{"seq": 999, "type": "bogus"\n')
    with open(path, "wb") as fh:
        fh.write(b"".join(lines))
    raised = False
    try:
        read_events(path)
    except TornMiddleError:
        raised = True
    fz.check(raised, f"seed {fz.seed}: middle tear did not raise")
    fz.middle_tears += 1
    with open(path, "wb") as fh:
        fh.write(data)
    back, torn = read_events_safe(path)
    fz.check(not torn and sequence_dense(back),
             f"seed {fz.seed}: restore failed after middle tear")


def run_fuzz(seed: int = 0, n_ops: int = 200, workdir: str = "") -> dict:
    """Fuzz one journal with ``n_ops`` seeded events; returns the verdict."""
    seed, n_ops = int(seed), int(n_ops)
    rng = random.Random(seed)
    wd = workdir or tempfile.mkdtemp(prefix=f"oax-fuzz-{seed}-")
    os.makedirs(wd, exist_ok=True)
    path = os.path.join(wd, f"fuzz-{seed}.jsonl")
    if os.path.exists(path):
        os.remove(path)

    fz = _Fuzz(seed)
    j = Journal(path)
    j.start_run(f"fuzz-{seed}")
    written = []
    for i in range(n_ops):
        payload = _rand_payload(rng)
        ev = j.append(TYPES[rng.randrange(len(TYPES))], payload)
        written.append((ev.seq, ev.type, dict(ev.payload)))
        fz.check(ev.seq == i, f"seed {seed}: seq {ev.seq} != {i} at op {i}")
        if i % 7 == 3:
            _torn_tail_cycle(fz, path, i + 1)
        if i % 11 == 5:
            _middle_tear_cycle(fz, path, rng)

    back, torn = read_events_safe(path)
    fz.check(not torn and sequence_dense(back) and len(back) == n_ops,
             f"seed {seed}: final journal not dense ({len(back)}/{n_ops})")
    fz.check([(e.seq, e.type, dict(e.payload)) for e in back] == written,
             f"seed {seed}: round-trip lost bytes (unicode/nesting?)")
    fz.check(replay(back) == replay(read_events(path)),
             f"seed {seed}: two reads folded to different replay state")

    return {
        "seed": seed,
        "n_ops": n_ops,
        "events_written": len(written),
        "torn_injected": fz.torn_injected,
        "middle_tears": fz.middle_tears,
        "checks_run": fz.checks,
        "violations": fz.violations,
        "roundtrip": not any("round-trip" in v for v in fz.violations),
        "dense": sequence_dense(back) if n_ops else True,
        "ok": not fz.violations,
        "journal": path,
    }


def run_fuzz_suite(seeds=(0, 1, 2), n_ops: int = 200, workdir: str = "") -> list:
    """Fuzz several seeds (fresh sub-workdir per seed) -> list of reports."""
    out = []
    for s in seeds:
        sub = os.path.join(workdir, f"seed-{s}") if workdir else ""
        out.append(run_fuzz(seed=s, n_ops=n_ops, workdir=sub))
    return out


def render_fuzz(r: dict) -> str:
    """Deterministic one-line verdict (no timings, ever)."""
    verdict = "OK" if r["ok"] else f"{len(r['violations'])} VIOLATION(S)"
    return (f"fuzz seed={r['seed']:<4} ops={r['n_ops']:<5} "
            f"torn={r['torn_injected']:<4} middle={r['middle_tears']:<3} "
            f"events={r['events_written']:<5} checks={r['checks_run']:<5} "
            f"roundtrip={r['roundtrip']} -> {verdict}")
