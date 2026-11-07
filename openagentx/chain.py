"""Hash-chained traces — tamper evidence over the append-only journal.

The journal is append-only with dense sequences; a hash chain makes edits
*detectable and localizable*: each chained line carries
``"chain": {"prev", "digest"}`` where ``digest`` covers the previous line's
digest plus the event's full canonical JSON (seq, run_id, type, payload,
ts). Editing any stored byte of event *k* changes ``digest_k``'s input, so
line *k+1* no longer links to it — :func:`verify_journal` names exactly
where the chain breaks.

Contracts:

- **Genesis convention**: the first line chains from ``GENESIS`` (64 zeros)
  — deterministic, no hidden seed.
- **Old readers stay compatible**: the chain lives in an extra top-level
  key; ``Event.from_json`` ignores it, so every existing reader (views,
  replay, compaction, drills) reads chained journals unchanged.
- **Two-layer verification**: (A) every stored ``prev`` equals the
  recomputed digest of its predecessor — catches edits, deletions,
  reorders; (B) every stored ``digest`` recomputes from its own
  ``prev`` + event — catches partial rewrites. An attacker who rewrites
  the entire suffix consistently is only caught by anchoring the head
  externally (compare it against a previously reported head/seal).
- **Seal is loud**: :func:`seal` returns the head only of a fully intact,
  chain-written, non-torn journal; anything else raises
  :class:`ChainError` naming the problem. An empty journal has nothing to
  seal.
- **Plain journals verify too, honestly**: a legacy journal (no chain
  fields) reports ``chained: False`` — its seq density is checked and a
  recomputed head is reported, but interior tampering is not intrinsically
  detectable without stored digests.
- Pure stdlib: ``hashlib`` + ``json`` only; the stored ``ts`` is covered
  as-is (tampering with it is detectable too).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .events import Event, Journal, read_events_safe

GENESIS = "0" * 64


class ChainError(ValueError):
    """The journal's hash chain is broken (or the journal is unsealable)."""


def event_digest(prev: str, ev: Event) -> str:
    """sha256 over prev digest + the event's canonical JSON (all fields)."""
    return hashlib.sha256((prev + ev.to_json()).encode("utf-8")).hexdigest()


def compute_chain(events: list) -> list:
    """Cumulative digests for an event list (genesis-chained)."""
    out: list = []
    prev = GENESIS
    for ev in events:
        prev = event_digest(prev, ev)
        out.append(prev)
    return out


def head_of(events: list) -> str:
    """Head digest over an in-memory event list ("" for no events)."""
    chain = compute_chain(events)
    return chain[-1] if chain else ""


class ChainedJournal(Journal):
    """A journal whose every line carries ``{"prev", "digest"}`` integrity.

    Appends behave exactly like :class:`~openagentx.events.Journal` (same
    events, same dense seq, same readers); the only difference is the extra
    top-level ``chain`` key on disk and ``self.head`` tracking the latest
    digest. Resuming an existing journal continues its chain from the
    recomputed digest of the last line.
    """

    def __init__(self, path):
        super().__init__(path)
        self._prev = GENESIS
        events = read_events_safe(path)[0]
        if events:  # continue the chain from the last line's own digest
            self._prev = event_digest(self._stored_prev(path, len(events) - 1),
                                      events[-1])
        self.head = self._prev if events else ""

    @staticmethod
    def _stored_prev(path, index: int) -> str:
        """Stored ``chain.prev`` of line *index* (GENESIS for unchained)."""
        with open(path, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        for back in (0, -1):
            idx = index + back
            if 0 <= idx < len(lines):
                try:
                    chain = json.loads(lines[idx]).get("chain") or {}
                    if chain.get("prev"):
                        return str(chain["prev"])
                except json.JSONDecodeError:
                    continue
        return GENESIS

    def _line(self, ev: Event) -> str:
        digest = event_digest(self._prev, ev)
        obj = asdict(ev)
        obj["chain"] = {"prev": self._prev, "digest": digest}
        self._prev = digest
        self.head = digest
        return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def verify_journal(path) -> dict:
    """Recompute the chain from disk; report integrity honestly.

    Returns ``{"ok", "n", "head", "broken_at", "torn_tail", "chained"}``:
    - ``ok``: dense seq AND (when chained) every stored ``prev``/``digest``
      pair re-derives correctly.
    - ``broken_at``: first line index where verification failed (-1 when
      intact). Editing any stored byte of line *k* surfaces at *k* itself
      (its committed digest no longer re-derives); deleting or reordering
      surfaces at the first mislinked line.
    - ``torn_tail``: an undecodable trailing line was isolated; the intact
      prefix may still verify, but the file is incomplete and unsealable.
    - ``chained``: False for legacy journals without chain fields.
    """
    events, torn = read_events_safe(path)
    stored = _stored_chain(path)
    prev = GENESIS
    broken_at = -1
    for i, ev in enumerate(events):
        if broken_at >= 0:
            continue
        if ev.seq != i:
            broken_at = i  # seq gap/reorder: chain cannot be trusted past here
            continue
        recomputed = event_digest(prev, ev)
        if stored.get(i) is not None:
            if stored[i].get("prev") != prev or stored[i].get("digest") != recomputed:
                broken_at = i
                continue
        prev = recomputed
    chained = bool(events) and all(stored.get(i) for i in range(len(events)))
    ok = broken_at < 0
    head = prev if (ok and events) else ""
    return {"ok": ok, "n": len(events), "head": head, "broken_at": broken_at,
            "torn_tail": torn, "chained": chained}


def _stored_chain(path) -> dict:
    """Index → ``{"prev", "digest"}`` for every complete, parseable line."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return {}
    out: dict = {}
    for i, line in enumerate(ln for ln in raw.splitlines() if ln.strip()):
        try:
            chain = json.loads(line).get("chain")
        except json.JSONDecodeError:
            continue  # torn tail: verify_journal reports it via read_events_safe
        if isinstance(chain, dict) and chain.get("digest"):
            out[i] = {"prev": chain.get("prev"), "digest": str(chain["digest"])}
    return out


def seal(path) -> str:
    """Return the head digest of a fully intact, chain-written journal.

    Raises :class:`ChainError` naming the problem for broken chains, torn
    tails, legacy (unchained) journals, and empty journals — a seal over
    unverifiable bytes would be a lie.
    """
    report = verify_journal(path)
    if report["torn_tail"]:
        raise ChainError(f"journal {path}: torn tail; recover the prefix "
                         "before sealing")
    if not report["ok"]:
        raise ChainError(f"journal {path}: chain broken at index "
                         f"{report['broken_at']}")
    if report["n"] == 0:
        raise ChainError(f"journal {path}: empty; nothing to seal")
    if not report["chained"]:
        raise ChainError(f"journal {path}: not chain-written; refusing to "
                         "seal unverifiable bytes")
    return report["head"]


def chain_report(path) -> str:
    """One-line human summary of :func:`verify_journal` (deterministic)."""
    r = verify_journal(path)
    state = "ok" if r["ok"] else f"BROKEN at index {r['broken_at']}"
    torn = " +torn_tail" if r["torn_tail"] else ""
    chained = "chained" if r["chained"] else "plain"
    return f"chain {state}: {r['n']} events head={r['head'][:16]} {chained}{torn}"
