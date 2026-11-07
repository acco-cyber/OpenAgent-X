"""Property suite — the journal invariants hold after *every* step.

Where the fuzz harness attacks a *fixed schedule* (torn tail every 7th
op, middle tear every 11th), the property suite asks a sharper question:
after every single step of a *randomly generated* trace, do the
invariants still hold?  A seeded ``random.Random`` picks each operation
— append, torn-tail injection, writer restart — and after *every*
operation the suite re-reads the journal from disk and demands:

- **density**: the sequence is exactly ``0..n-1`` — never a gap, never a
  repeat, even across writer restarts and tear/recover cycles;
- **torn-tail safety**: injected garbage always isolates as a torn tail
  (strict readers refuse loudly), the intact prefix always comes back,
  and truncation restores the file to the *exact bytes* it had before
  the tear — byte-for-byte, not just event-for-event;
- **round-trip**: every ``(seq, type, payload)`` ever written is on disk
  after every step, unicode and nesting included — nothing lost, nothing
  invented;
- **replay clock-independence**: rewriting every ``ts`` in the journal
  to a different wall-clock folds to the *identical* replay state and
  the semantic diff calls the shifted journal the same — derived state
  is a function of events, never of the clock.

Determinism contract: the trace is fully determined by ``seed`` and
``n_ops``, and the report carries no timings, so the same seed always
yields the same verdict.
"""

from __future__ import annotations

import json
import os
import random
import tempfile

from .events import (Journal, TornMiddleError, read_events,
                     read_events_safe, sequence_dense)
from .jdiff import diff_events
from .trace import replay, truncate_torn_tail

TYPES = ("run_start", "step_start", "thought", "tool_call", "tool_result",
         "reply", "error", "budget", "note", "run_end")
ALPHABET = ("abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_{}\"'\\éπ漢字☃")
TOOLS = ("calc", "write_file", "read_file", "think")
# Torn-tail garbage: undecodable fragments with NO newline, so the tear
# always lands on the final line and truncate_torn_tail can restore it.
GARBAGE = (b'{"seq": 999, "typ',
           b'{"seq":4 , "type": "note", "payl',
           b'not json at all',
           b'{"seq": 12, "type":')

# op-kind lottery: 0-69 append, 70-87 torn tail, 88-99 writer restart.
_P_APPEND, _P_TORN = 70, 88


def _rand_str(rng: random.Random) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(rng.randrange(0, 20)))


def _rand_payload(rng: random.Random) -> dict:
    kind = rng.randrange(6)
    if kind == 0:
        return {}
    if kind == 1:
        return {"note": _rand_str(rng)}
    if kind == 2:
        return {"tool": rng.choice(TOOLS), "args": {"x": rng.randrange(1000)}}
    if kind == 3:
        return {"ok": rng.random() < 0.5,
                "result": {"n": rng.randrange(100), "text": _rand_str(rng)}}
    if kind == 4:
        return {"nested": {"deep": {"list": [_rand_str(rng)
                                             for _ in range(rng.randrange(4))]}}}
    return {"expr": f"{rng.randrange(99)}*{rng.randrange(99)}",
            "tags": [_rand_str(rng), rng.random()]}


def _canon(ev) -> tuple:
    """Comparable (seq, type, canonical-payload) tuple for a written event."""
    return (ev.seq, ev.type,
            json.dumps(ev.payload, sort_keys=True, ensure_ascii=False))


class _Prop:
    """Mutable accumulator for one property trace (violations + counters)."""

    def __init__(self, seed: int):
        self.seed = seed
        self.violations: list = []
        self.checks = 0
        self.appends = 0
        self.torn_injected = 0
        self.torn_isolated = 0
        self.byte_exact_resumes = 0
        self.resumes = 0
        self.reads_checked = 0
        self.strict_refusals = 0

    def check(self, ok: bool, what: str) -> None:
        self.checks += 1
        if not ok:
            self.violations.append(what)


def _torn_cycle(pr: _Prop, path: str, rng: random.Random, expected: int,
                op: int) -> None:
    """Inject garbage at the tail; isolation + strict refusal + exact bytes."""
    pre = open(path, "rb").read() if os.path.exists(path) else b""
    with open(path, "ab") as fh:
        fh.write(rng.choice(GARBAGE))
    pr.torn_injected += 1

    back, torn = read_events_safe(path)
    if torn and len(back) == expected:
        pr.torn_isolated += 1
    pr.check(torn and len(back) == expected,
             f"seed {pr.seed}: tear at op {op} not isolated "
             f"(torn={torn}, len={len(back)}, want {expected})")

    raised = False
    try:
        read_events(path)
    except TornMiddleError:
        raised = True
    if raised:
        pr.strict_refusals += 1
    pr.check(raised, f"seed {pr.seed}: strict reader tolerated a "
                     f"torn tail at op {op}")

    if truncate_torn_tail(path):
        now = open(path, "rb").read()
        if now == pre:
            pr.byte_exact_resumes += 1
        pr.check(now == pre,
                 f"seed {pr.seed}: truncation did not restore the exact "
                 f"pre-tear bytes at op {op}")
    else:
        pr.check(False, f"seed {pr.seed}: truncation removed nothing "
                        f"at op {op}")


def run_property_trace(seed: int = 0, n_ops: int = 80, workdir: str = "") -> dict:
    """Drive one random trace; verify the invariants after every step."""
    seed, n_ops = int(seed), int(n_ops)
    rng = random.Random(seed ^ 0x5EED)  # distinct stream from the fuzz harness
    wd = workdir or tempfile.mkdtemp(prefix=f"oax-property-{seed}-")
    os.makedirs(wd, exist_ok=True)
    path = os.path.join(wd, f"property-{seed}.jsonl")
    if os.path.exists(path):
        os.remove(path)

    pr = _Prop(seed)
    j = Journal(path)
    j.start_run(f"property-{seed}")
    written: list = []
    expected = 0

    for i in range(n_ops):
        op = rng.randrange(100)
        if op < _P_APPEND:
            ev = j.append(TYPES[rng.randrange(len(TYPES))], _rand_payload(rng))
            written.append(_canon(ev))
            expected += 1
            pr.appends += 1
        elif op < _P_TORN:
            _torn_cycle(pr, path, rng, expected, i)
        else:
            j = Journal(path)  # fresh writer must resume the dense sequence
            j.start_run(f"property-{seed}")
            pr.resumes += 1
            back, torn = read_events_safe(path)
            pr.check(not torn and len(back) == expected and sequence_dense(back),
                     f"seed {pr.seed}: resume state wrong at op {i} "
                     f"(torn={torn}, len={len(back)}, want {expected})")

        # Every step ends with a full read-back: density, round-trip and
        # two independent folds must hold *now*, not just at the end.
        back, torn = read_events_safe(path)
        pr.reads_checked += 1
        pr.check(not torn and sequence_dense(back) and len(back) == expected,
                 f"seed {pr.seed}: density broken at op {i} "
                 f"(torn={torn}, len={len(back)}, want {expected})")
        pr.check([_canon(e) for e in back] == written,
                 f"seed {pr.seed}: round-trip mismatch at op {i}")
        pr.check(replay(back) == replay(read_events(path)),
                 f"seed {pr.seed}: two reads folded to different state "
                 f"at op {i}")

    # Replay clock-independence: rewrite every ts on disk to a different
    # wall-clock; the fold and the semantic diff must not notice.
    final_events = read_events(path)
    back, torn = read_events_safe(path)
    pr.check(not torn and sequence_dense(back)
             and len(back) == len(final_events),
             f"seed {pr.seed}: final read not clean")
    pr.check(replay(final_events) == replay(read_events(path)),
             f"seed {pr.seed}: final two reads folded to different state")
    shifted_path = os.path.join(wd, f"property-{seed}.ts-shifted.jsonl")
    with open(shifted_path, "w", encoding="utf-8") as fh:
        for e in final_events:
            d = json.loads(e.to_json())
            d["ts"] = e.ts + 1717.25 + e.seq
            fh.write(json.dumps(d, sort_keys=True, ensure_ascii=False) + "\n")
    shifted = read_events(shifted_path)
    ts_invariant = (len(shifted) == len(final_events)
                    and replay(shifted) == replay(final_events)
                    and diff_events(shifted, final_events)["same"])
    pr.check(ts_invariant,
             f"seed {pr.seed}: replay depends on wall-clock ts")

    back, torn = read_events_safe(path)
    return {
        "seed": seed,
        "n_ops": n_ops,
        "appends": pr.appends,
        "torn_injected": pr.torn_injected,
        "torn_isolated": pr.torn_isolated,
        "strict_refusals": pr.strict_refusals,
        "byte_exact_resumes": pr.byte_exact_resumes,
        "resumes": pr.resumes,
        "reads_checked": pr.reads_checked,
        "checks_run": pr.checks,
        "events_written": len(written),
        "violations": pr.violations,
        "dense": not torn and sequence_dense(back),
        "ts_invariant": ts_invariant,
        "ok": not pr.violations,
        "journal": path,
    }


def run_property_suite(seeds=(0, 1, 2), n_ops: int = 80, workdir: str = "") -> list:
    """Run the property trace for several seeds (fresh sub-workdir each)."""
    out = []
    for s in seeds:
        sub = os.path.join(workdir, f"seed-{s}") if workdir else ""
        out.append(run_property_trace(seed=s, n_ops=n_ops, workdir=sub))
    return out


def render_property(r: dict) -> str:
    """Deterministic one-line verdict (no timings, ever)."""
    verdict = "OK" if r["ok"] else f"{len(r['violations'])} VIOLATION(S)"
    return (f"property seed={r['seed']:<4} ops={r['n_ops']:<4} "
            f"appends={r['appends']:<4} torn={r['torn_injected']:<3} "
            f"resumes={r['resumes']:<3} reads={r['reads_checked']:<5} "
            f"checks={r['checks_run']:<5} ts-invariant={r['ts_invariant']} "
            f"-> {verdict}")
