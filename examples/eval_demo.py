#!/usr/bin/env python3
"""X-Eval demo — golden tasks, graded offline.

Runs the shipped golden-task suite end-to-end: a baseline EchoLLM finish,
a scripted tool loop, a guardrail refusal, and a budget stop — each task is
JSON, each expectation is checked against the real trace, and the report is
reproducible JSON (kernel version + config included).

    python examples/eval_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openagentx.evaluation import render_text, run_suite, save_report  # noqa: E402


def main() -> None:
    report = run_suite()  # resolves ./golden_tasks or the repo copy
    print(render_text(report))

    with tempfile.TemporaryDirectory() as td:
        out = save_report(report, Path(td) / "eval-report.json")
        assert out.stat().st_size > 500, "report suspiciously small"
        assert report["summary"]["failed"] == 0, "golden suite must fully pass offline"
        print(f"\nreport: {out.name} — {len(report['tasks'])} tasks, "
              f"pass_rate {report['summary']['pass_rate']:.0%}, offline={report['offline']}")
        print("add a task: copy one JSON in golden_tasks/, set expectations, `oax eval`")


if __name__ == "__main__":
    main()
