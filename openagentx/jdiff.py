"""Event-level journal diff — semantic comparison of two event streams.

The journal is the single source of truth, so comparing two runs means
comparing their event streams. Wall-clock ``ts`` is noise between two real
runs, so the default *semantic* projection ignores it; ``strict`` mode
compares every stored field (useful for byte-level forensics on copies).

Determinism contract: the same pair of journals always yields the same
report dict and the same rendered text — no wall-clock, no dict order,
no locale.

Diff semantics (aligned with diff(1) where it makes sense):

- the **common prefix** is the longest leading run of events whose projected
  forms are equal;
- ``removed`` / ``added`` carry the diverging tails of A and B respectively;
- ``same`` is True iff both tails are empty;
- a self-diff is always ``same`` with ``diverged_at == -1``.
"""

from __future__ import annotations

import json
import os

from .events import read_events_safe, sequence_dense

#: Fields treated as wall-clock noise in semantic mode.
DEFAULT_IGNORE = ("ts",)


def _projected(ev, ignore) -> str:
    """Canonical projected form of one event (comparison key)."""
    from dataclasses import asdict

    d = asdict(ev)
    for k in ignore:
        d.pop(k, None)
    return json.dumps(d, sort_keys=True, ensure_ascii=False)


def _summary(ev) -> dict:
    """Renderable, honest summary of one event (payload kept intact)."""
    return {"seq": ev.seq, "type": ev.type, "payload": dict(ev.payload or {})}


def _type_counts(events) -> dict:
    counts: dict = {}
    for ev in events:
        counts[ev.type] = counts.get(ev.type, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def diff_events(a: list, b: list, ignore=("ts",)) -> dict:
    """Diff two event streams under a projection that drops ``ignore`` keys."""
    pa = [_projected(ev, ignore) for ev in a]
    pb = [_projected(ev, ignore) for ev in b]
    n = 0
    for x, y in zip(pa, pb):
        if x != y:
            break
        n += 1
    removed = [_summary(ev) for ev in a[n:]]
    added = [_summary(ev) for ev in b[n:]]
    same = n == len(a) == len(b)
    return {
        "same": same,
        "common": n,
        "diverged_at": -1 if same else n,
        "events_a": len(a),
        "events_b": len(b),
        "removed": removed,
        "added": added,
        "removed_count": len(removed),
        "added_count": len(added),
        "type_counts_a": _type_counts(a),
        "type_counts_b": _type_counts(b),
        "ignore": list(ignore),
    }


def diff_journals(path_a, path_b, strict: bool = False) -> dict:
    """Diff two journal files; torn tails are isolated, never silently dropped.

    ``strict=True`` compares every stored field (including ``ts``); the
    default semantic mode ignores wall-clock noise.
    """
    for p in (path_a, path_b):
        if not os.path.exists(p):
            raise FileNotFoundError(f"journal {p} does not exist")
    ea, torn_a = read_events_safe(path_a)
    eb, torn_b = read_events_safe(path_b)
    ignore = () if strict else DEFAULT_IGNORE
    d = diff_events(ea, eb, ignore=ignore)
    d["journal_a"] = str(path_a)
    d["journal_b"] = str(path_b)
    d["torn_a"] = torn_a
    d["torn_b"] = torn_b
    d["dense_a"] = sequence_dense(ea)
    d["dense_b"] = sequence_dense(eb)
    return d


def _line(ev: dict, mark: str) -> str:
    body = json.dumps(ev["payload"], sort_keys=True, ensure_ascii=False)
    if len(body) > 72:
        body = body[:69] + "..."
    return f"{mark} seq={ev['seq']:<3} {ev['type']:<14} {body}"


def render_diff(d: dict) -> str:
    """Deterministic human-readable rendering of a diff report."""
    out: list = []
    a = d.get("journal_a", "<stream-a>")
    b = d.get("journal_b", "<stream-b>")
    out.append(f"diff {a} {b}")
    out.append(f"mode: ignore={d['ignore']}")
    torn = []
    if d.get("torn_a"):
        torn.append("a")
    if d.get("torn_b"):
        torn.append("b")
    out.append(f"events: a={d['events_a']} b={d['events_b']} "
               f"common={d['common']} torn=[{','.join(torn)}]")
    if d["same"]:
        out.append("verdict: SAME (semantically identical event streams)")
    else:
        out.append(f"verdict: DIFFERENT (diverged at seq {d['diverged_at']})")
        for ev in d["removed"]:
            out.append(_line(ev, "-"))
        for ev in d["added"]:
            out.append(_line(ev, "+"))
    counts_a = d.get("type_counts_a", {})
    counts_b = d.get("type_counts_b", {})
    all_types = sorted(set(counts_a) | set(counts_b))
    if all_types:
        out.append("type counts (a / b):")
        for t in all_types:
            ca, cb = counts_a.get(t, 0), counts_b.get(t, 0)
            delta = "" if ca == cb else f"  ({'+' if cb > ca else ''}{cb - ca})"
            out.append(f"  {t:<14} {ca:>4} / {cb:>4}{delta}")
    return "\n".join(out)
