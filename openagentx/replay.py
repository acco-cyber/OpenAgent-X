"""X-View: replay any run as a timeline — terminal text and a self-contained HTML page.

The other half of X-Trace's promise: a trace you cannot *see* is a trace
you will not audit. This module is a pure consumer of the append-only JSONL
event stream — it never writes to traces and adds no new event types:

* :func:`load_timeline` parses any ``TraceLog`` file into offsets from the
  run's first event, tolerating torn tail lines (they render as corrupt
  markers instead of killing the replay — same rule as ``TraceLog.replay``).
* :func:`render_text` draws an aligned terminal timeline (+ms offsets).
* :func:`render_html` renders a **self-contained** dark-mode HTML page —
  inline CSS only, zero JavaScript, zero CDN assets — with per-namespace
  color coding, a proportional run "sparkline", and payloads expandable via
  native ``<details>`` elements. Share it, attach it to an incident, or
  open it in any browser offline.

Everything re-runs :func:`openagentx.events.redact` on payload rendering as
defense in depth (traces are already redacted at the write boundary).
"""

from __future__ import annotations

import html
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openagentx.events import redact

DEFAULT_REPLAY_DIR = ".openagentx/replays"

# Event namespace → (chip color, label) for the HTML view. One hue per
# subsystem so a glance answers "which subsystem dominated this run?".
_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("task.", "#60a5fa", "task lifecycle"),
    ("kernel.", "#a78bfa", "kernel loop"),
    ("agent.", "#22d3ee", "model / tool calls"),
    ("policy.", "#fbbf24", "policy verdicts"),
    ("execution.", "#34d399", "execution"),
    ("artifact.", "#34d399", "artifacts"),
    ("verification.", "#2dd4bf", "verification"),
    ("mem.", "#f472b6", "memory"),
    ("pack.", "#fb923c", "knowledge packs"),
    ("subtask.", "#818cf8", "delegation"),
)


def _category(event_type: str) -> tuple[str, str]:
    for prefix, color, label in _CATEGORIES:
        if event_type.startswith(prefix):
            return color, label
    return "#94a3b8", "other"


def _parse_time(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


@dataclass
class TimelineEvent:
    """One event positioned on the run's time axis."""

    sequence: int
    event_type: str
    actor: str
    occurred_at: str
    payload: dict[str, Any] = field(default_factory=dict)
    offset_ms: float | None = None     # ms since the run's first event
    corrupt: bool = False              # torn/unparsable trace line

    @property
    def color(self) -> str:
        return _category(self.event_type)[0]


@dataclass
class Timeline:
    """A whole run laid out on one time axis."""

    path: Path
    events: list[TimelineEvent]
    run_id: str
    started_at: str | None
    duration_ms: float
    counts: Counter

    @property
    def corrupt_lines(self) -> int:
        return sum(1 for e in self.events if e.corrupt)

    def summary_line(self) -> str:
        return (
            f"run {self.run_id} — {len(self.events)} events, "
            f"{self.duration_ms:.0f} ms wall clock ({self.path})"
        )


def load_timeline(path: str | Path) -> Timeline:
    """Parse a trace JSONL file into a :class:`Timeline`.

    Offsets are relative to the first parsable event's timestamp; events
    without a parsable timestamp keep ``offset_ms=None`` and render first.
    """
    path = Path(path)
    events: list[TimelineEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            events.append(
                TimelineEvent(
                    sequence=int(data["sequence"]),
                    event_type=str(data["event_type"]),
                    actor=f"{data['actor']['type']}:{data['actor']['id']}",
                    occurred_at=str(data.get("occurred_at", "")),
                    payload=dict(data.get("payload") or {}),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            events.append(
                TimelineEvent(sequence=-1, event_type="trace.corrupt_line", actor="?:?", occurred_at="", corrupt=True)
            )

    t0: datetime | None = None
    for event in events:
        when = _parse_time(event.occurred_at)
        if when is not None:
            t0 = when
            break  # first parsable timestamp anchors the axis

    for event in events:
        when = _parse_time(event.occurred_at)
        if t0 is not None and when is not None:
            event.offset_ms = (when - t0).total_seconds() * 1000.0

    times = [_parse_time(e.occurred_at) for e in events]
    times = [t for t in times if t is not None]
    duration_ms = (max(times) - min(times)).total_seconds() * 1000.0 if times else 0.0
    counts = Counter(e.event_type for e in events)
    return Timeline(
        path=path,
        events=events,
        run_id=path.stem,
        started_at=events[0].occurred_at if events else None,
        duration_ms=duration_ms,
        counts=counts,
    )


# ------------------------------------------------------------------- text


def render_text(timeline: Timeline, limit: int | None = None) -> str:
    """Aligned terminal timeline. ``limit=None`` shows every event."""
    lines = [timeline.summary_line()]
    shown = timeline.events if limit is None else timeline.events[:limit]
    for event in shown:
        offset = "  +?ms" if event.offset_ms is None else f"+{event.offset_ms:4.0f}ms"
        payload = json.dumps(redact(event.payload), ensure_ascii=False)
        lines.append(
            f"  #{event.sequence:03d} {offset:8s} {event.event_type:30s} [{event.actor}] {payload[:110]}"
        )
    if limit is not None and len(timeline.events) > limit:
        lines.append(f"  … {len(timeline.events) - limit} more events (HTML view has everything)")
    return "\n".join(lines)


# ------------------------------------------------------------------- html


_CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #0b1120; color: #e2e8f0;
       font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
header { padding: 20px 24px 12px; border-bottom: 1px solid #1e293b; }
h1 { margin: 0 0 4px; font-size: 16px; letter-spacing: .5px; }
h1 span { color: #64748b; font-weight: normal; }
.meta { color: #94a3b8; font-size: 12px; }
.lane { position: relative; height: 26px; margin: 14px 0 4px;
        background: #111a2e; border: 1px solid #1e293b; border-radius: 6px; overflow: hidden; }
.lane i { position: absolute; top: 6px; width: 8px; height: 14px; border-radius: 2px;
          min-width: 2px; transform: translateX(-50%); }
.legend { color: #64748b; font-size: 11px; margin-bottom: 16px; }
.legend b { font-weight: normal; margin-right: 12px; white-space: nowrap; }
.legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; }
.chips { margin: 0 0 14px; }
.chip { display: inline-block; margin: 2px 6px 2px 0; padding: 1px 8px; border-radius: 10px;
        background: #16203a; border: 1px solid #23304f; color: #cbd5e1; font-size: 11px; }
ol { list-style: none; margin: 0; padding: 0 24px 40px; position: relative; }
ol::before { content: ""; position: absolute; left: 33px; top: 8px; bottom: 40px;
             width: 2px; background: #1e293b; }
li { position: relative; padding: 3px 0 3px 26px; }
li .dot { position: absolute; left: 3px; top: 8px; width: 10px; height: 10px; border-radius: 50%;
          border: 2px solid #0b1120; }
li .seq { color: #64748b; display: inline-block; width: 40px; }
li .off { color: #475569; display: inline-block; width: 74px; }
li summary { cursor: pointer; list-style: none; display: inline; }
li summary:hover .etype { text-decoration: underline; }
li .etype { font-weight: bold; }
li .actor { color: #64748b; }
li .actor::before { content: " · "; color: #334155; }
details[open] summary ~ .payload { display: block; }
.payload { margin: 6px 0 10px 40px; padding: 10px 12px; background: #0f172a;
           border: 1px solid #1e293b; border-radius: 6px; white-space: pre-wrap;
           word-break: break-word; color: #94a3b8; font-size: 12px; max-width: 980px; }
.corrupt .etype { color: #f87171 !important; }
@media print { body { background: #fff; color: #111; } .lane, .legend, .chip { border-color: #ddd; } }
"""


def render_html(timeline: Timeline) -> str:
    """Self-contained HTML timeline: inline CSS, no JavaScript, no CDN."""
    esc = html.escape

    # proportional sparkline: one tick per event, positioned by time offset
    span = timeline.duration_ms or 1.0
    ticks = []
    for event in timeline.events:
        pos = 1.0 if event.offset_ms is None else max(event.offset_ms, 0.0) / span * 100.0
        ticks.append(
            f'<i style="left:{pos:.2f}%;background:{event.color}" '
            f'title="#{event.sequence} {esc(event.event_type)}"></i>'
        )

    legend, seen = [], set()
    for event in timeline.events:
        color, label = _category(event.event_type)
        if label not in seen:
            seen.add(label)
            legend.append(f"<b><i style='background:{color}'></i>{esc(label)}</b>")

    chips = "".join(
        f"<span class='chip'>{esc(t)} × {n}</span>"
        for t, n in timeline.counts.most_common()
    )

    rows = []
    for event in timeline.events:
        offset = "?" if event.offset_ms is None else f"{event.offset_ms:.0f} ms"
        payload = json.dumps(redact(event.payload), indent=2, ensure_ascii=False)
        corrupt = " class='corrupt'" if event.corrupt else ""
        rows.append(
            f"<li{corrupt}>"
            f"<span class='dot' style='background:{event.color}'></span>"
            f"<span class='seq'>#{event.sequence:03d}</span>"
            f"<span class='off'>+{offset}</span>"
            f"<details><summary><span class='etype' style='color:{event.color}'>"
            f"{esc(event.event_type)}</span><span class='actor'>{esc(event.actor)}</span></summary>"
            f"<div class='payload'>{esc(payload)}</div></details></li>"
        )

    started = esc(timeline.started_at or "?")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>OpenAgent-X run {esc(timeline.run_id)}</title><style>{_CSS}</style></head><body>"
        "<header><h1>⚡ OpenAgent-X run timeline "
        f"<span>· {esc(timeline.run_id)}</span></h1>"
        f"<div class='meta'>{timeline.summary_line()} · started {started}</div>"
        f"<div class='lane'>{''.join(ticks)}</div>"
        f"<div class='legend'>{''.join(legend)}</div>"
        f"<div class='chips'>{chips}</div>"
        f"</header><ol>{''.join(rows)}</ol></body></html>"
    )


def replay_to_html(trace_path: str | Path, out: str | Path | None = None) -> Path:
    """Render a trace file to an HTML timeline, returning the output path.

    Default output: ``.openagentx/replays/<run_id>.html`` (next to nothing
    else — the page is a single file, easy to share or attach).
    """
    timeline = load_timeline(trace_path)
    target = Path(out) if out else Path(DEFAULT_REPLAY_DIR) / f"{timeline.run_id}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(timeline), encoding="utf-8")
    return target
