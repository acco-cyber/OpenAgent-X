#!/usr/bin/env python3
"""X-View demo — replay any run as a timeline.

Runs a real kernel task offline (EchoLLM, zero API keys), then turns the
resulting trace into both timeline views: aligned terminal text and a
self-contained HTML page (inline CSS, no JavaScript, no CDN — open it
anywhere, attach it to an incident, commit it to a postmortem).

    python examples/replay_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openagentx.budget import Budget  # noqa: E402
from openagentx.builtins import register_builtins  # noqa: E402
from openagentx.llm import EchoLLM  # noqa: E402
from openagentx.loop import AgentKernel  # noqa: E402
from openagentx.policy import default_policy  # noqa: E402
from openagentx.replay import load_timeline, render_html, render_text, replay_to_html  # noqa: E402
from openagentx.tools import ToolRegistry  # noqa: E402
from openagentx.trace import TraceLog  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1) produce a real trace with the full kernel, fully offline
        trace = TraceLog(path=tmp / "replay-demo.jsonl")
        registry = ToolRegistry(policy=default_policy(), trace=trace)
        register_builtins(registry, include_exec=False, include_network=False)
        kernel = AgentKernel(
            EchoLLM(),
            trace,
            tools=registry,
            budget=Budget(max_iterations=4),
        )
        kernel.run("Summarize this workspace, then finish.")
        print("trace produced:", trace.path.name)

        # 2) terminal timeline
        timeline = load_timeline(trace.path)
        print(render_text(timeline))

        # 3) self-contained HTML timeline
        html_path = replay_to_html(trace.path, out=tmp / "replay-demo.html")
        page = html_path.read_text(encoding="utf-8")
        assert len(page) > 2_000, "HTML timeline suspiciously small"
        assert page.count("<li") == len(timeline.events), "HTML rows must match events"
        assert "doctype html" in page[:40].lower() and "cdn" not in page.lower()
        print(f"\nHTML timeline: {html_path.stat().st_size:,} bytes, "
              f"{timeline.events[0].event_type} → … → {timeline.events[-1].event_type}")
        print("open it in any browser — one file, zero dependencies")


if __name__ == "__main__":
    main()
