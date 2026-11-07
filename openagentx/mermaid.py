"""Mermaid trace export — the journal as a deterministic flowchart.

One node per event (id ``E{seq:03d}``, label = seq + type + redacted,
truncated payload) and one spine edge per consecutive pair — the causal
chain of the run. Labels are quote-escaped and newline-stripped so the
exported file is always valid Mermaid; extension event types (``hook``,
``tool_disclose``, ``budget``, ...) render through the same generic
path as core types. No timestamps, no ids beyond ``seq`` — same events
in, byte-identical text out. The export is a *view*: it re-uses report's
redaction helpers, so even a pre-redaction journal cannot leak a secret
through a diagram.
"""

from __future__ import annotations

import html
import json

from .report import _clean, _short

_LABEL = 64


def _label(ev) -> str:
    """One-line, escaped, truncated node label for one event."""
    p = _clean(ev.payload)
    if ev.type == "tool_result":
        body = p.get("result", p.get("error", ""))
        detail = json.dumps(body, sort_keys=True, ensure_ascii=False)
    else:
        detail = json.dumps(p, sort_keys=True, ensure_ascii=False)
    text = _short(detail, _LABEL)
    text = html.escape(text, quote=True)
    text = text.replace("\r", " ").replace("\n", " ")
    text = "".join(c for c in text if ord(c) >= 32)
    return f"{ev.seq:03d} {ev.type} {text}".strip()


def _cls(ev) -> str:
    """Deterministic style class for one event (empty = default)."""
    if ev.type == "error":
        return "err"
    if ev.type == "tool_result" and (ev.payload or {}).get("ok") is False:
        return "fail"
    if ev.type == "tool_call":
        return "call"
    if ev.type in ("reply", "run_end"):
        return "say"
    return ""


def render_mermaid(events: list, title: str = "OpenAgent-X trace") -> str:
    """Canonical Mermaid export: nodes, spine edges, classed styling."""
    lines: list = ["flowchart TD"]
    lines.append(f"%% {title} - {len(events)} events")
    for ev in events:
        lines.append(f'  E{ev.seq:03d}["{_label(ev)}"]')
    for a, b in zip(events, events[1:]):
        lines.append(f"  E{a.seq:03d} --> E{b.seq:03d}")
    groups: dict = {}
    for ev in events:
        c = _cls(ev)
        if c:
            groups.setdefault(c, []).append(f"E{ev.seq:03d}")
    lines.append("  classDef call fill:#1e3a5f,stroke:#7aa2f7,color:#d7dae0")
    lines.append("  classDef fail fill:#5f1e2e,stroke:#e06c75,color:#d7dae0")
    lines.append("  classDef err fill:#6b2f3a,stroke:#e06c75,color:#d7dae0")
    lines.append("  classDef say fill:#1e5f3a,stroke:#98c379,color:#d7dae0")
    for c in sorted(groups):
        lines.append(f"  class {','.join(groups[c])} {c}")
    if not events:
        lines.append("  %% empty journal: zero events, zero spine")
    return "\n".join(lines) + "\n"


def trace_mermaid(path, title: str = "OpenAgent-X trace") -> str:
    """Load a journal (torn tails isolate the prefix) and export Mermaid."""
    from .trace import load_trace

    events, _torn = load_trace(path)
    return render_mermaid(events, title=title)
