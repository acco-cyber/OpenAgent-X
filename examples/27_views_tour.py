"""Offline example 27 — one run, every view: the flight-recorder tour.

One real offline run — a secret read, a think, a planned failure, a
reply — and then every read-only view this repository ships, all over
that single journal: the text timeline, the report render, the stats
fingerprint, grep, the self-diff, the fold from the middle, the
self-contained dashboard, the mermaid spine. Three claims are checked
across the whole tour: every view renders byte-identically twice (views
are functions of events, never of the clock); every counter comes from
the same replay fold (stats and the fold can never disagree); and the
raw fixture token appears in none of the renders — one truth, many
windows, no leaks.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.dashboard import dashboard_sha256, render_dashboard
from openagentx.grep import grep_journal, render_grep
from openagentx.jdiff import diff_journals, render_diff
from openagentx.mermaid import render_mermaid
from openagentx.replay import replay_from, render_replay
from openagentx.report import render_text
from openagentx.runner import AgentRunner
from openagentx.llm import ScriptedLLM
from openagentx.stats import render_stats, run_stats
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace, replay, text_timeline


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-27-")
    jp = os.path.join(wd, "journal.jsonl")

    # the one real run every view will read
    script = [
        {"action": {"tool": "vault_read", "args": {"key": "github"}},
         "thought": "fetch the token"},
        {"action": {"tool": "think", "args": {"note": "use it carefully"}},
         "thought": "plan"},
        {"action": {"tool": "read_file", "args": {"path": "gone.txt"}},
         "thought": "planned failure"},
        {"reply": "tour complete"},
    ]
    runner = AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                         max_steps=8)
    result = runner.run("views tour")
    assert result.stop_reason == "reply"

    events, torn = load_trace(jp)
    assert torn is False and len(events) == 16  # 1 + 3 action turns x4 + 3 tail
    state = replay(events)
    assert state["tool_calls"] == 3 and state["tool_fails"] == 1
    assert state["replies"] == 1 and state["runs_closed"] == 1

    # 1) timeline + report: byte-identical re-renders
    t1, t2 = text_timeline(jp), text_timeline(jp)
    assert t1 == t2 and "vault_read" in t1 and "gone.txt" in t1
    r1, r2 = render_text(events), render_text(events)
    assert r1 == r2
    print("timeline + report: byte-identical re-renders")

    # 2) stats: the fingerprint IS the fold's counters
    s = run_stats(jp)
    assert s["events"] == len(events) and s["steps"] == 4
    assert s["tool_calls"] == state["tool_calls"] == 3
    assert s["redactions"] == 1 and s["tools"]["read_file"]["failed"] == 1
    sr1, sr2 = render_stats(s), render_stats(s)
    assert sr1 == sr2
    print("stats: counters taken from the same replay fold")

    # 3) grep: the failed read names itself, the secret stays a marker
    g = grep_journal(jp, tool="read_file")
    assert g["matched"] == 2  # the tool_call AND its failed tool_result
    gjoin = "".join(g["matches"])
    assert '"ok": false' in gjoin
    gsecret = grep_journal(jp, tool="vault_read")
    secret_view = render_grep(gsecret)
    raw = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    assert raw not in secret_view and "[REDACTED:github_token]" in secret_view
    print("grep: call+result pair matched, raw token prints only redacted")

    # 4) self-diff: the zero diff, semantic and strict
    d = diff_journals(jp, jp)
    assert d["same"] and d["diverged_at"] == -1 and d["removed_count"] == 0
    assert diff_journals(jp, jp, strict=True)["same"]
    dr1, dr2 = render_diff(d), render_diff(d)
    assert dr1 == dr2
    print("self-diff: the zero diff, even in strict mode")

    # 5) fold from the middle: additivity where it is true, honestly
    r0 = replay_from(jp, 0)
    assert r0["folded"] == r0["total"] == len(events)
    assert r0["state"]["tool_calls"] == state["tool_calls"]
    mid = replay_from(jp, from_seq=5)  # second action turn's step_start
    assert mid["folded"] == len(events) - 5 == 11
    assert mid["state"]["tool_calls"] == 2  # whole (3) minus prefix (1)
    try:
        replay_from(jp, from_seq=len(events))
        raise AssertionError("out-of-bounds must raise, never clamp")
    except ValueError:
        pass
    rr1, rr2 = render_replay(mid), render_replay(mid)
    assert rr1 == rr2 and "replay --from 5" in rr1
    print("replay-from: 11 of 16 folded, counters additive, bounds loud")

    # 6) dashboard: self-contained HTML, stable sha256, no external URLs
    h1, h2 = render_dashboard(jp), render_dashboard(jp)
    assert h1 == h2 and dashboard_sha256(jp) == dashboard_sha256(jp)
    assert "<script" not in h1 and "http://" not in h1 and "https://" not in h1
    print("dashboard: one self-contained file, stable sha256")

    # 7) mermaid: one node per event on the spine
    m1, m2 = render_mermaid(events), render_mermaid(events)
    assert m1 == m2 and m1.splitlines()[0] == "flowchart TD"
    nodes = [ln for ln in m1.splitlines()
             if ln.strip().startswith("E") and '["' in ln]
    assert len(nodes) == len(events)  # node per event, zero-padded
    print("mermaid: flowchart TD, one zero-padded node per event")

    # 8) the tour-wide leak sweep: the raw token lives in no view at all
    everything = t1 + r1 + sr1 + secret_view + dr1 + rr1 + h1 + m1
    assert raw not in everything
    assert "[REDACTED:github_token]" in everything  # the boundary held
    print("leak sweep: raw token in none of the 8 views, marker present")

    print("OK 27_views_tour (one run, every view, one truth, no leaks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
