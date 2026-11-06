"""Human views over journals: text timeline and self-contained HTML report.

Both renderers re-apply redaction on payloads (defense in depth: even if a
pre-redaction journal is ever handed to a renderer, secrets still cannot leak
into a view). The HTML is fully self-contained — inline CSS, zero external
assets, everything HTML-escaped, no timestamps shown (views must be
deterministic for a given event list).
"""

from __future__ import annotations

import html
import json

from .redact import redact_obj

_TRUNC = 240


def _clean(payload: dict):
    p, _ = redact_obj(payload)
    return p


def _short(s: str, limit: int = _TRUNC) -> str:
    s = str(s)
    return s if len(s) <= limit else s[: limit - 3] + "..."


def render_text(events: list) -> str:
    """Deterministic one-line-per-event timeline."""
    lines: list = []
    for ev in events:
        p = _clean(ev.payload)
        if ev.type == "run_start":
            lines.append(f"[{ev.seq:03d}] RUN   task={_short(p.get('task', ''))}")
        elif ev.type == "step_start":
            lines.append(f"[{ev.seq:03d}] STEP  {p.get('step')}")
        elif ev.type == "thought":
            lines.append(f"[{ev.seq:03d}] THINK {_short(p.get('text', ''))}")
        elif ev.type == "tool_call":
            lines.append(
                f"[{ev.seq:03d}] CALL  {p.get('tool')} args={_short(json.dumps(p.get('args', {}), sort_keys=True, ensure_ascii=False))}"
            )
        elif ev.type == "tool_result":
            body = p.get("result", p.get("error", ""))
            lines.append(
                f"[{ev.seq:03d}] OBS   {p.get('tool')} ok={p.get('ok')} {_short(json.dumps(body, sort_keys=True, ensure_ascii=False))}"
            )
        elif ev.type == "reply":
            lines.append(f"[{ev.seq:03d}] REPLY {_short(p.get('text', ''))}")
        elif ev.type == "run_end":
            lines.append(f"[{ev.seq:03d}] END   {p.get('stop_reason')}")
        elif ev.type == "error":
            lines.append(f"[{ev.seq:03d}] ERROR {_short(p.get('error', ''))}")
        else:
            lines.append(f"[{ev.seq:03d}] {ev.type.upper():<5} {_short(json.dumps(p, sort_keys=True, ensure_ascii=False))}")
    return "\n".join(lines)


_CSS = """body{font-family:ui-monospace,Menlo,Consolas,monospace;background:#0f1115;
color:#d7dae0;margin:0;padding:24px;line-height:1.5}
h1{font-size:18px;color:#fff}
table{border-collapse:collapse;width:100%;max-width:1100px}
td{padding:4px 10px;border-bottom:1px solid #23262e;vertical-align:top;white-space:pre-wrap;
word-break:break-word}
td.seq{color:#6b7280;width:52px}td.type{color:#7aa2f7;width:84px;font-weight:600}
tr.reply td{background:#1a2b1f}tr.error td{background:#2b1a1e}
.small{color:#6b7280;font-size:12px}"""


def render_html(events: list, title: str = "OpenAgent-X trace") -> str:
    """Self-contained HTML timeline: inline CSS, escaped payloads, no assets."""
    rows: list = []
    for ev in events:
        p = _clean(ev.payload)
        if ev.type == "tool_result":
            body = p.get("result", p.get("error", ""))
            detail = json.dumps(body, sort_keys=True, ensure_ascii=False)
        else:
            detail = json.dumps(p, sort_keys=True, ensure_ascii=False)
        cls = ""
        if ev.type in ("reply", "run_end"):
            cls = ' class="reply"'
        elif ev.type == "error":
            cls = ' class="error"'
        rows.append(
            f'<tr{cls}><td class="seq">{ev.seq:03d}</td>'
            f'<td class="type">{html.escape(ev.type)}</td>'
            f"<td>{html.escape(_short(detail))}</td></tr>"
        )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f"<p class=\"small\">{len(events)} events &middot; self-contained "
        "(inline CSS, escaped payloads, zero external assets)</p>"
        f"<table>{''.join(rows)}</table></body></html>"
    )
