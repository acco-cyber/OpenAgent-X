"""Golden-task evaluation — honest, offline, deterministic drills.

Protocol:
- Every golden task is a JSON spec driving a *real* execution offline
  (``ScriptedLLM`` + builtin tools), graded by a drill of named checks.
- Drill exceptions are folded into a single failing ``harness_error`` check —
  a crashed drill can never look green.
- Grading is honest: a check is green only if the behavior was actually
  observed in this run. No caching, no snapshots, no skipped asserts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .events import Journal, sequence_dense
from .llm import ScriptedLLM
from .redact import REDACTED_PREFIX
from .runner import AgentRunner, RESERVED_TOOLS
from .team import TeamRunner
from .tools import builtin_tools, vault_value
from .trace import load_trace, replay, truncate_torn_tail, view

MARKER = REDACTED_PREFIX
WORKROOT_ENV = "OAX_DRILL_ROOT"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class DrillReport:
    task_id: str
    drill: str
    checks: list

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)


def _fold(task: dict, drill_fn) -> list:
    """Run a drill, folding any crash into a failing harness_error check."""
    try:
        return list(drill_fn(task))
    except Exception as e:  # noqa: BLE001 — honest folding, never silent green
        return [Check("harness_error", False, f"{type(e).__name__}: {e}")]


def _script(task: dict) -> list:
    return [str(line) for line in task.get("script", [])]


def _expect(task: dict) -> dict:
    return dict(task.get("expect", {}))


def _run_offline(task: dict, wd: str, journal: str = "journal.jsonl"):
    """Execute the task script offline; returns (events, result)."""
    runner = AgentRunner(
        ScriptedLLM(_script(task)),
        builtin_tools(wd),
        os.path.join(wd, journal),
        max_steps=int(task.get("max_steps", 8)),
        max_tool_calls=int(task.get("max_tool_calls", 0)),
        workdir=wd,
        run_id=str(task.get("run_id", "drill-1")),
    )
    result = runner.run(str(task.get("task_text", "offline drill")))
    events, _torn = load_trace(os.path.join(wd, journal))
    return events, result


def _fresh_wd(kind: str) -> str:
    """Isolated per-invocation workspace: drills never reuse state."""
    import tempfile

    if os.environ.get(WORKROOT_ENV):
        wd = os.path.join(os.environ[WORKROOT_ENV], kind + "-" + tempfile.mkdtemp()[1:])
        os.makedirs(wd, exist_ok=True)
        return wd
    return tempfile.mkdtemp(prefix=f"oax-{kind}-")


def _reopen(journal_path: str) -> list:
    events, _torn = load_trace(journal_path)
    return events


def _loop_drill(task: dict) -> list:
    wd = _fresh_wd("loop")
    events, result = _run_offline(task, wd)
    exp = _expect(task)
    types = [ev.type for ev in events]
    n_actions = sum(
        1 for line in _script(task)
        if "action" in json.loads(line) and json.loads(line)["action"].get("tool") not in RESERVED_TOOLS
    )
    checks = [
        Check("journal_written", len(events) > 0, f"{len(events)} events"),
        Check("run_start_present", types[0] == "run_start"),
        Check("stop_reason_matches", result.stop_reason == exp.get("stop_reason", "reply"),
              f"got {result.stop_reason} want {exp.get('stop_reason', 'reply')}"),
        Check("sequence_dense", sequence_dense(events)),
        Check("steps_match_script", result.steps == exp.get("steps", len(_script(task))),
              f"steps={result.steps}"),
        Check("tool_calls_match",
              sum(1 for e in events if e.type == "tool_call") == exp.get("tool_calls", n_actions)),
        Check("events_end_with_run_end", types[-1] == "run_end"),
        Check("journal_reopen_dense", sequence_dense(_reopen(os.path.join(wd, "journal.jsonl")))),
    ]
    if "reply" in exp:
        checks.append(Check("reply_text_matches", result.reply == exp["reply"],
                            f"got {result.reply!r} want {exp['reply']!r}"))
    return checks


def _redact_drill(task: dict) -> list:
    wd = _fresh_wd("redact")
    tok = vault_value("github")
    with open(os.path.join(wd, "note.txt"), "w", encoding="utf-8") as fh:
        fh.write("github token: " + tok + "\n")
    events, result = _run_offline(task, wd)
    journal_raw = open(os.path.join(wd, "journal.jsonl"), encoding="utf-8").read()
    tview = view(events, "text")
    hview = view(events, "html")
    plain_note = str(task.get("plain_note", "plain note about token budgets"))
    return [
        Check("stop_reason_matches", result.stop_reason == _expect(task).get("stop_reason", "reply")),
        Check("raw_token_absent_in_journal", tok not in journal_raw),
        Check("journal_has_redaction_marker", f"{MARKER}github_token]" in journal_raw),
        Check("redaction_count_recorded",
              any(int((e.payload or {}).get("redactions", 0) or 0) >= 1
                  for e in events if e.type == "tool_result")),
        Check("report_text_redacted", tok not in tview and f"{MARKER}github_token]" in tview),
        Check("report_html_redacted",
              tok not in hview and MARKER in hview and "github_token]" in hview),
        Check("file_keeps_raw_truth", tok in open(os.path.join(wd, "note.txt"), encoding="utf-8").read()),
        Check("no_false_positive", any(
            e.type == "thought" and e.payload.get("text", "").find(plain_note) >= 0 for e in events
        )),
    ]


def _trace_drill(task: dict) -> list:
    wd = _fresh_wd("trace")
    jp = os.path.join(wd, "journal.jsonl")
    events, result = _run_offline(task, wd)
    n_before = len(events)
    types_before = [e.type for e in events]
    with open(jp, "a", encoding="utf-8") as fh:
        fh.write('{"seq": 999, "torn": tru')  # crash mid-write
    torn_events, torn = load_trace(jp)
    s1, s2 = replay(torn_events), replay(torn_events)
    tview = view(torn_events, "text")
    hview = view(torn_events, "html")
    truncated = truncate_torn_tail(jp)
    j2 = Journal(jp)
    j2.start_run("resume-1")
    tail = j2.append("note", {"resume": True})
    resumed = j2.events()
    reply_text = _expect(task).get("reply", result.reply)
    return [
        Check("torn_tail_isolated", torn and len(torn_events) == n_before, f"torn={torn}"),
        Check("prefix_events_intact", [e.type for e in torn_events] == types_before),
        Check("sequence_dense", sequence_dense(torn_events)),
        Check("replay_deterministic", s1 == s2),
        Check("replay_state_sane",
              s1["replies"] == 1 and s1["final_stop"] == "reply"),
        Check("views_agree", reply_text in tview and reply_text in hview),
        Check("html_self_contained", 'src="http' not in hview and 'href="http' not in hview),
        Check("torn_tail_truncated", truncated is True),
        Check("resume_continues", tail.seq == n_before and sequence_dense(resumed)),
    ]


def _team_drill(task: dict) -> list:
    """Two-role handoff: lead writes a brief, specialist consumes it — one journal."""
    wd = _fresh_wd("team")
    lead = ScriptedLLM([str(s) for s in task.get("lead_script", [])], name="lead")
    spec = ScriptedLLM([str(s) for s in task.get("specialist_script", [])], name="specialist")
    runner = TeamRunner(
        lead, spec, builtin_tools(wd), os.path.join(wd, "journal.jsonl"),
        max_steps_per_role=int(task.get("max_steps_per_role", 6)),
        workdir=wd, run_id=str(task.get("run_id", "team-drill")),
    )
    result = runner.run(str(task.get("task_text", "team handoff drill")))
    events, _torn = load_trace(os.path.join(wd, "journal.jsonl"))
    handoffs = [e for e in events if e.type == "handoff"]
    h = handoffs[0].payload if handoffs else {}
    role_starts = [e.payload.get("role") for e in events if e.type == "role_start"]
    replies = [e for e in events if e.type == "reply"]
    brief_path = os.path.join(wd, "brief.txt")
    lead_writes = [e for e in events if e.type == "tool_call"
                   and e.payload.get("role") == "lead"
                   and e.payload.get("tool") == "write_file"]
    spec_reads = [e for e in events if e.type == "tool_result"
                  and e.payload.get("role") == "specialist"
                  and e.payload.get("tool") == "read_file" and e.payload.get("ok")]
    brief_on_disk = open(brief_path, encoding="utf-8").read() if os.path.exists(brief_path) else ""
    jp = os.path.join(wd, "journal.jsonl")
    return [
        Check("journal_dense_shared", sequence_dense(events), f"{len(events)} events"),
        Check("handoff_event_present",
              len(handoffs) == 1 and h.get("from_role") == "lead"
              and h.get("to_role") == "specialist", str(h)[:80]),
        Check("handoff_reason_recorded", bool(h.get("reason")), str(h.get("reason", ""))[:60]),
        Check("role_phases_ordered", role_starts == ["lead", "specialist"], str(role_starts)),
        Check("lead_wrote_brief", bool(lead_writes) and "brief: compute 6*7" in brief_on_disk,
              f"writes={len(lead_writes)} disk={brief_on_disk[:30]!r}"),
        Check("specialist_read_brief",
              bool(spec_reads) and "brief: compute 6*7" in str((spec_reads[0].payload.get("result") or {}).get("text", "")),
              "observation flows through the journal"),
        Check("reply_after_handoff",
              bool(replies) and bool(handoffs) and replies[0].seq > handoffs[0].seq
              and replies[0].payload.get("role") == "specialist"),
        Check("final_stop_reply",
              result.stop_reason == "reply" and events[-1].payload.get("stop_reason") == "reply",
              f"got {result.stop_reason}"),
        Check("single_run_shared_truth", len({e.run_id for e in events}) == 1,
              "one journal, one run identity"),
        Check("reopen_dense", sequence_dense(_reopen(jp))),
    ]


def _router_drill(task: dict) -> list:
    """Multi-model fallback: primary fails loudly, fallback serves, exhaustion is explicit."""
    from .router import FailingLLM, FallbackRouter, ModelUnavailable

    wd = _fresh_wd("router")
    fb_script = [str(s) for s in task.get("fallback_script", [])]
    # 1) direct routing observation
    router = FallbackRouter([("primary", FailingLLM("primary")),
                             ("fallback", ScriptedLLM(fb_script, name="fallback"))])
    routed = router.complete([{"role": "user", "content": "route this turn"}])
    # 2) probe: a failing adapter raises loudly on direct call
    probe = FailingLLM("probe")
    raised = ""
    try:
        probe.complete([])
    except ModelUnavailable as e:
        raised = f"{type(e).__name__}: {e}"
    # 3) end-to-end: runner with router answers via fallback
    wd_run = os.path.join(wd, "journal.jsonl")
    router2 = FallbackRouter([("primary", FailingLLM("primary")),
                              ("fallback", ScriptedLLM(fb_script, name="fallback"))])
    result = AgentRunner(router2, builtin_tools(wd), wd_run,
                         max_steps=int(task.get("max_steps", 6)), workdir=wd,
                         run_id="router-drill").run(str(task.get("task_text", "routed run")))
    events, _torn = load_trace(wd_run)
    # 4) exhaustion: every adapter down -> explicit model_unavailable stop
    router3 = FallbackRouter([("a", FailingLLM("a")), ("b", FailingLLM("b"))])
    result3 = AgentRunner(router3, builtin_tools(wd), os.path.join(wd, "exhaust.jsonl"),
                          max_steps=6, workdir=wd, run_id="router-exhaust").run("doomed run")
    events3, _t3 = load_trace(os.path.join(wd, "exhaust.jsonl"))
    exp = _expect(task)
    want_reply = str(exp.get("reply", ""))
    return [
        Check("primary_fails_loudly", raised.startswith("ModelUnavailable:"), raised[:80]),
        Check("fallback_serves", "reply" in routed and routed["reply"] == want_reply,
              str(routed)[:60]),
        Check("attempts_recorded",
              [a["model"] for a in router.log] == ["primary", "fallback"]
              and router.log[0]["ok"] is False and router.log[1]["ok"] is True,
              str(router.log)[:100]),
        Check("failure_reason_honest", "ModelUnavailable" in router.log[0]["error"]),
        Check("runner_reply_via_fallback", result.stop_reason == "reply" and result.reply == want_reply,
              f"got {result.stop_reason}"),
        Check("router_log_grew_in_run", len(router2.log) == 2, f"{len(router2.log)} attempts"),
        Check("exhaustion_stop_reason",
              result3.stop_reason == "model_unavailable"
              and events3[-1].payload.get("stop_reason") == "model_unavailable",
              f"got {result3.stop_reason}"),
        Check("exhaustion_error_event",
              any(e.type == "error" and "NoModelAvailable" in str(e.payload.get("error", ""))
                  for e in events3)),
        Check("exhaustion_never_replies", not any(e.type == "reply" for e in events3)),
        Check("journals_dense_reopen",
              sequence_dense(events) and sequence_dense(events3)
              and sequence_dense(_reopen(os.path.join(wd, "exhaust.jsonl")))),
    ]


DRILLS = {
    "loop": _loop_drill,
    "redact": _redact_drill,
    "trace": _trace_drill,
    "team": _team_drill,
    "router": _router_drill,
}


def run_golden_task(task_path: str) -> DrillReport:
    with open(task_path, encoding="utf-8") as fh:
        task = json.load(fh)
    drill_name = str(task.get("drill", ""))
    drill = DRILLS.get(drill_name)
    if drill is None:
        return DrillReport(str(task.get("id", task_path)), drill_name,
                           [Check("unknown_drill", False, f"no drill named '{drill_name}'")])
    return DrillReport(str(task.get("id", task_path)), drill_name, _fold(task, drill))


def list_golden_tasks(tasks_dir: str = "golden_tasks") -> list:
    if not os.path.isdir(tasks_dir):
        return []
    return sorted(
        os.path.join(tasks_dir, f) for f in os.listdir(tasks_dir) if f.endswith(".json")
    )


def run_eval(tasks_dir: str = "golden_tasks") -> tuple:
    """Run every golden task. Returns (reports, all_ok)."""
    reports = [run_golden_task(p) for p in list_golden_tasks(tasks_dir)]
    all_ok = bool(reports) and all(r.ok for r in reports)
    return reports, all_ok
