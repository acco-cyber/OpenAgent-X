"""Journal grep — the journal is searchable truth, not just replayable truth.

Grep reads the journal from disk and filters its events with plain,
deterministic matchers: a case-sensitive substring ``pattern`` over the
event's searchable projection (type + payload JSON), an exact ``etype``,
an exact ``tool`` name, a ``since_seq`` floor and a ``limit`` cap — all
AND-ed together. Matches render through the redaction engine before they
leave the module: raw secrets live on disk (the boundary redacts tool
results, not free-form thoughts), so a search view that printed matches
verbatim would be a leak channel. Grep is a view like every other view —
defense in depth holds. Same journal, same matchers, same bytes out: no
timestamps, no dict-order surprises. Torn tails are isolated, never
searched, only reported. The honest empty result is ``matched: 0`` with
the scanned total named — never fabricated.
"""

from __future__ import annotations

import json

from .redact import redact
from .trace import load_trace


def _searchable(ev) -> str:
    """The event's searchable projection: type + payload JSON, key-sorted."""
    return json.dumps({"type": ev.type, "payload": ev.payload},
                      sort_keys=True, ensure_ascii=False)


def grep_journal(path: str, pattern: str = "", etype: str = "",
                 tool: str = "", since_seq: int = 0,
                 limit: int = 0) -> dict:
    """Filter one journal's events; report matches honestly and redacted.

    ``pattern`` is a case-sensitive substring over the searchable
    projection; ``etype`` matches the event type exactly; ``tool`` matches
    the payload's ``tool`` field exactly (tool_call and tool_result alike);
    ``since_seq`` keeps seq >= N; ``limit`` keeps the first N matches in
    seq order (0 = uncapped). Returns the match report dict — the matches
    already redacted, the counters raw truth.
    """
    events, torn = load_trace(path)
    hits = []
    for ev in events:
        if etype and ev.type != etype:
            continue
        if tool and (ev.payload or {}).get("tool") != tool:
            continue
        if since_seq and ev.seq < since_seq:
            continue
        if pattern and pattern not in _searchable(ev):
            continue
        hits.append(ev)
    if limit and len(hits) > limit:
        hits = hits[:limit]

    matches = []
    redactions = 0
    for ev in hits:
        raw_line = json.dumps({"seq": ev.seq, "type": ev.type,
                               "payload": ev.payload},
                              sort_keys=True, ensure_ascii=False)
        line, n = redact(raw_line)
        redactions += n
        matches.append(line)

    return {
        "matches": matches,
        "matched": len(matches),
        "total": len(events),
        "torn_tail": bool(torn),
        "redactions": redactions,
        "pattern": pattern,
        "etype": etype,
        "tool": tool,
        "since_seq": int(since_seq or 0),
        "limit": int(limit or 0),
    }


def render_grep(report: dict) -> str:
    """Deterministic text render: header, then one redacted line per match.

    The header names matched/total, the torn-tail isolation and the limit
    when one applied; an empty result says so honestly instead of printing
    nothing at all.
    """
    head = (f"grep: {report['matched']}/{report['total']} events matched")
    if report["torn_tail"]:
        head += " [torn tail isolated]"
    if report["limit"]:
        head += f" [limit {report['limit']}]"
    lines = [head]
    for m in report["matches"]:
        lines.append(m)
    if not report["matches"]:
        lines.append("no matches — the honest empty result")
    return "\n".join(lines) + "\n"
