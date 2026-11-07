"""Offline example 24 — oax grep: searchable truth that cannot leak.

The journal is searchable truth, not just replayable truth. This example
runs a real offline run, then searches it: matchers AND together
(substring over the type+payload JSON, exact event type, exact tool name,
a seq floor, a seq-ordered cap), the empty result is honest, and — the
point of the whole feature — a raw token hand-written into a journal at
runtime matches on disk (the disk is the truth) yet prints only the
redacted form, even when the search pattern IS the raw token itself.
"""

import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.cli import main as cli_main
from openagentx.events import Journal
from openagentx.grep import grep_journal, render_grep
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-24-")
    jp = os.path.join(wd, "journal.jsonl")

    # one real run: a secret read, a file write, a think, a reply
    script = [
        {"thought": "read the secret",
         "action": {"tool": "vault_read", "args": {"key": "github"}}},
        {"thought": "write it",
         "action": {"tool": "write_file",
                    "args": {"path": "a.txt", "text": "hi"}}},
        {"thought": "plan",
         "action": {"tool": "think", "args": {"note": "search me"}}},
        {"reply": "searched"},
    ]
    runner = AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                         max_steps=6)
    result = runner.run("grep demo")
    assert result.stop_reason == "reply"

    # filter by type: every tool_call, in seq order
    by_type = grep_journal(jp, etype="tool_call")
    assert by_type["matched"] == 3
    assert all('"type": "tool_call"' in m for m in by_type["matches"])

    # filter by tool: covers tool_call AND tool_result pairs
    by_tool = grep_journal(jp, tool="write_file")
    assert by_tool["matched"] == 2

    # matchers AND together: one write_file tool_result survives both
    both = grep_journal(jp, etype="tool_result", tool="write_file")
    assert both["matched"] == 1 and '"ok": true' in both["matches"][0]

    # seq floor + cap: the first kept match is the real first survivor
    capped = grep_journal(jp, etype="tool_call", since_seq=4, limit=1)
    assert capped["matched"] == 1 and '"seq": 7' in capped["matches"][0]

    # the empty result is honest, never fabricated
    none = grep_journal(jp, pattern="zzz-not-in-this-journal")
    assert none["matched"] == 0 and none["matches"] == []
    assert "no matches" in render_grep(none) and str(none["total"]) in render_grep(none)

    # defense in depth: a raw token on disk never leaves the view
    raw = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    leak = os.path.join(wd, "leak.jsonl")
    lj = Journal(leak)
    lj.start_run("leak")
    lj.append("thought", {"text": "token " + raw})
    g1 = grep_journal(leak, pattern="token ")
    assert g1["matched"] == 1 and raw not in "".join(g1["matches"])
    assert "[REDACTED:github_token]" in g1["matches"][0]
    # even when the pattern IS the raw token: matches on disk, prints redacted
    g2 = grep_journal(leak, pattern=raw)
    assert g2["matched"] == 1 and raw not in "".join(g2["matches"])

    # the CLI agrees: exit 0 matched / 1 none / 1 missing, stdout redacted
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert cli_main(["grep", jp, "--type", "tool_call"]) == 0
        assert cli_main(["grep", jp, "--pattern", "zzz"]) == 1
        assert cli_main(["grep", os.path.join(wd, "gone.jsonl")]) == 1
        assert cli_main(["grep", leak, "--pattern", "token "]) == 0
    so = buf.getvalue()
    assert raw not in so and "[REDACTED:github_token]" in so

    # and the real drill grades green: all twelve checks
    from openagentx.evaluation import run_golden_task
    with redirect_stdout(io.StringIO()):
        report = run_golden_task(os.path.join(
            os.path.dirname(__file__), "..", "golden_tasks",
            "37-grep-journal.json"))
    assert report.ok, f"grep drill red: {[c.name for c in report.checks if not c.ok]}"
    assert len(report.checks) == 12 and report.passed == 12

    print("grep: 3 tool_calls by type, 2 write_file events by tool, "
          "AND-joins to 1, since+limit keeps seq 7, honest empty, "
          "raw token matched on disk and printed redacted (2 searches)")
    print("drill 37-grep-journal: 12/12 checks green")
    print("OK 24_grep_journal (searchable truth whose search view cannot leak)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
