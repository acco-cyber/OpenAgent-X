"""Report v2 — a deterministic HTML dashboard over one journal.

``report.py`` renders a timeline; the dashboard is the *v2* view: an
integrity strip, summary cards, a per-type distribution with bars, a
per-tool table and the full escaped timeline, all in one self-contained
file (inline CSS, zero external assets, everything HTML-escaped, no
timestamps shown). Every counter is taken from ``stats.run_stats`` —
which itself takes replay's numbers — so the dashboard, stats and
replay can never disagree (one source of truth). Wall-clock duration is
reported honestly and never graded. The determinism contract: the same
file in, byte-identical HTML and JSON out, always.
"""

from __future__ import annotations

import hashlib
import html
import json

from .report import _clean, _short
from .stats import run_stats

_TRUNC = 240


def dashboard_data(path) -> dict:
    """The dashboard's numbers: exactly ``run_stats`` (replay's counters)."""
    return run_stats(path)


def dashboard_json(path) -> str:
    """Canonical JSON form of the dashboard data (sorted keys, stable)."""
    return json.dumps(dashboard_data(path), sort_keys=True, ensure_ascii=False)


def dashboard_sha256(path) -> str:
    """sha256 over the rendered dashboard HTML — the determinism fingerprint."""
    return hashlib.sha256(render_dashboard(path).encode("utf-8")).hexdigest()


def _bar(count: int, total: int, max_count: int) -> str:
    """Deterministic distribution bar derived from integer counts only."""
    if max_count <= 0 or total <= 0:
        return ""
    width = int(round(100.0 * count / max_count))
    pct = 100.0 * count / total
    return (f'<div class="bar" style="width:{width}%"></div>'
            f'<span class="pct">{count} ({pct:.1f}%)</span>')


_CSS = """body{font-family:ui-monospace,Menlo,Consolas,monospace;background:#0f1115;
color:#d7dae0;margin:0;padding:24px;line-height:1.5}
h1{font-size:18px;color:#fff}h2{font-size:14px;color:#9aa4b2;margin:28px 0 8px}
.strip{padding:8px 12px;border:1px solid #23262e;background:#151821;max-width:1100px}
.strip.ok{border-color:#2f5d40}.strip.bad{border-color:#6b2f3a}
.cards{display:flex;flex-wrap:wrap;gap:8px;max-width:1100px}
.card{border:1px solid #23262e;background:#151821;padding:10px 14px;min-width:110px}
.card b{display:block;font-size:20px;color:#fff}.card span{color:#6b7280;font-size:11px}
table{border-collapse:collapse;width:100%;max-width:1100px}
td,th{padding:4px 10px;border-bottom:1px solid #23262e;vertical-align:top;text-align:left;
white-space:pre-wrap;word-break:break-word}
th{color:#6b7280;font-size:11px}td.seq{color:#6b7280;width:52px}td.type{color:#7aa2f7;
width:84px;font-weight:600}tr.reply td{background:#1a2b1f}tr.error td{background:#2b1a1e}
.bar{height:12px;background:#7aa2f7;display:inline-block;min-width:2px;vertical-align:middle}
.pct{color:#6b7280;font-size:11px;margin-left:6px;vertical-align:middle}
.small{color:#6b7280;font-size:12px}
.brow{margin:6px 0;max-width:1100px}.blabel{display:inline-block;width:130px;color:#9aa4b2}"""


def render_dashboard(path, title: str = "OpenAgent-X dashboard") -> str:
    """Self-contained HTML dashboard: escaped payloads, inline CSS, no assets."""
    d = dashboard_data(path)
    events, torn = _load(path)
    integ = "ok" if (d["dense"] and not d["torn_tail"]) else "bad"

    cards = [
        ("events", d["events"]), ("steps", d["steps"]), ("thoughts", d["thoughts"]),
        ("tool_calls", d["tool_calls"]), ("tool_fails", d["tool_fails"]),
        ("replies", d["replies"]), ("errors", d["errors"]),
        ("redactions", d["redactions"]), ("budgets", d["budgets"]),
        ("hooks", d["hooks"]), ("runs opened", d["runs_opened"]),
        ("runs closed", d["runs_closed"]),
    ]
    cards_html = "".join(
        f'<div class="card"><b>{html.escape(str(v))}</b>'
        f"<span>{html.escape(k)}</span></div>"
        for k, v in cards
    )

    total = d["events"]
    max_count = max(d["type_counts"].values()) if d["type_counts"] else 0
    bars = "".join(
        f'<div class="brow"><span class="blabel">{html.escape(k)}</span>'
        f"{_bar(v, total, max_count)}</div>"
        for k, v in d["type_counts"].items()
    ) or '<p class="small">no events</p>'

    tool_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{t['calls']}</td>"
        f"<td>{t['ok']}</td><td>{t['failed']}</td></tr>"
        for name, t in d["tools"].items()
    ) or '<tr><td colspan="4" class="small">no tool calls</td></tr>'

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
            f"<td>{html.escape(_short(detail, _TRUNC))}</td></tr>"
        )

    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f'<p class="strip {integ}">{d["events"]} events &middot; '
        f'dense={d["dense"]} &middot; torn_tail={d["torn_tail"]} &middot; '
        f'duration={d["duration"]}s (wall-clock, reported not graded)</p>'
        f'<h2>summary</h2><div class="cards">{cards_html}</div>'
        f"<h2>event types</h2>{bars}"
        f"<h2>tools</h2><table><tr><th>tool</th><th>calls</th><th>ok</th>"
        f"<th>failed</th></tr>{tool_rows}</table>"
        "<h2>timeline</h2><table><tr><th>seq</th><th>type</th>"
        f"<th>payload (redacted, escaped)</th></tr>{''.join(rows)}</table>"
        '<p class="small">self-contained: inline CSS, zero external assets, '
        "counters from replay (one source of truth)</p>"
        "</body></html>"
    )


def _load(path):
    from .events import read_events_safe

    return read_events_safe(path)
