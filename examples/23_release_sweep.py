"""Offline example 23 — the release sweep: one run, every view, one truth.

Before a release, OpenAgent-X re-demands its core invariants in a single
drill (golden task 36, ``sweep``). This example performs the sweep's story
itself against a real run: the stats and dashboard counters agree with the
raw event stream, every view re-renders byte-identically, the journal
self-diff is the zero diff, a raw token hand-written into a journal at
runtime is re-redacted by both rendered views, and ``__version__`` matches
the top CHANGELOG entry so release metadata cannot drift from the code.
Finally it grades the real drill and demands all twelve checks green.
"""

import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.dashboard import dashboard_data, render_dashboard
from openagentx.evaluation import run_golden_task
from openagentx.events import Journal
from openagentx.jdiff import diff_journals
from openagentx.llm import ScriptedLLM
from openagentx.mermaid import trace_mermaid
from openagentx.runner import AgentRunner
from openagentx.stats import run_stats
from openagentx.tools import builtin_tools

GOLDEN = os.path.join(os.path.dirname(__file__), "..", "golden_tasks",
                      "36-release-sweep.json")
CHANGELOG = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-23-")
    jp = os.path.join(wd, "journal.jsonl")

    # one real run: a secret read, a think, a planned failure, a reply
    script = [
        {"thought": "read the secret",
         "action": {"tool": "vault_read", "args": {"key": "github"}}},
        {"thought": "sweep every view",
         "action": {"tool": "think", "args": {"note": "2+2=4"}}},
        {"thought": "planned failure",
         "action": {"tool": "read_file", "args": {"path": "gone.txt"}}},
        {"reply": "swept"},
    ]
    runner = AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                         max_steps=6)
    result = runner.run("release sweep demo")
    assert result.stop_reason == "reply", f"stop={result.stop_reason}"

    events, torn = [], []
    from openagentx.trace import load_trace
    events, torn = load_trace(jp)
    assert not torn and [e.seq for e in events] == list(range(len(events))), \
        "the journal lands dense"

    # one source of truth: stats and dashboard counters match the raw stream
    st = run_stats(jp)
    d = dashboard_data(jp)
    counts = {}
    for ev in events:
        counts[ev.type] = counts.get(ev.type, 0) + 1
    assert d["events"] == st["events"] == len(events)
    assert d["tool_calls"] == st["tool_calls"] == 3   # think counts as a tool
    assert d["tool_fails"] == st["tool_fails"] == 1
    assert d["redactions"] == st["redactions"] >= 1
    assert d["type_counts"] == counts

    # every view re-renders byte-identically (a function of events, not clock)
    assert render_dashboard(jp) == render_dashboard(jp)
    assert trace_mermaid(jp) == trace_mermaid(jp)

    # the self-diff is the zero diff
    assert diff_journals(jp, jp)["same"] is True
    from openagentx.cli import main as cli_main
    with redirect_stdout(io.StringIO()):
        assert cli_main(["diff", jp, jp]) == 0

    # defense in depth: a runtime-assembled raw token never reaches a view
    raw = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    leak = os.path.join(wd, "leak.jsonl")
    lj = Journal(leak)
    lj.start_run("leak")
    lj.append("thought", {"text": "token " + raw})
    assert raw not in render_dashboard(leak)
    assert raw not in trace_mermaid(leak)
    assert "[REDACTED:github_token]" in render_dashboard(leak)
    assert "[REDACTED:github_token]" in trace_mermaid(leak)

    # release metadata cannot drift: __version__ is the top CHANGELOG entry
    from openagentx import __version__
    with open(CHANGELOG, encoding="utf-8") as fh:
        top = ""
        for line in fh:
            s = line.strip()
            if s.startswith("## [") and "]" in s:
                top = s[4:s.index("]")]
                break
    assert top == __version__, f"changelog {top} != __version__ {__version__}"

    # and the real drill grades green: all twelve checks, no exceptions
    with redirect_stdout(io.StringIO()):
        report = run_golden_task(GOLDEN)
    assert report.ok, f"sweep drill red: {[c.name for c in report.checks if not c.ok]}"
    assert len(report.checks) == 12 and report.passed == 12

    print(f"run: 12 events dense, counters agree, views deterministic, "
          f"self-diff SAME, raw token re-redacted by 2 views, "
          f"version {__version__} == changelog")
    print(f"drill 36-release-sweep: 12/12 checks green")
    print("OK 23_release_sweep (one run, every view, one truth, gates green)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
