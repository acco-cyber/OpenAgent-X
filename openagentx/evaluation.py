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
import re
from dataclasses import dataclass

from .audit import run_audit
from .events import Journal, read_events_safe, sequence_dense
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
    """Two-role handoff: lead writes a brief, specialist consumes it — one journal.

    Honest contract: exactly one reserved ``handoff`` event (lead→specialist,
    reason recorded), role phases ordered, the lead's brief reaches disk and the
    specialist reads it back through the journal, the reply comes after the
    handoff and matches ``expect.reply`` — all on one dense shared journal.
    """
    wd = _fresh_wd("team")
    exp = _expect(task)
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
    brief_marker = str(exp.get("brief_marker", "brief: compute 6*7"))
    brief_path = os.path.join(wd, "brief.txt")
    lead_writes = [e for e in events if e.type == "tool_call"
                   and e.payload.get("role") == "lead"
                   and e.payload.get("tool") == "write_file"]
    spec_reads = [e for e in events if e.type == "tool_result"
                  and e.payload.get("role") == "specialist"
                  and e.payload.get("tool") == "read_file" and e.payload.get("ok")]
    brief_on_disk = open(brief_path, encoding="utf-8").read() if os.path.exists(brief_path) else ""
    jp = os.path.join(wd, "journal.jsonl")
    checks = [
        Check("journal_dense_shared", sequence_dense(events), f"{len(events)} events"),
        Check("handoff_event_present",
              len(handoffs) == 1 and h.get("from_role") == "lead"
              and h.get("to_role") == "specialist", str(h)[:80]),
        Check("handoff_reason_recorded", bool(h.get("reason")), str(h.get("reason", ""))[:60]),
        Check("role_phases_ordered", role_starts == ["lead", "specialist"], str(role_starts)),
        Check("lead_wrote_brief", bool(lead_writes) and brief_marker in brief_on_disk,
              f"writes={len(lead_writes)} disk={brief_on_disk[:30]!r}"),
        Check("specialist_read_brief",
              bool(spec_reads) and brief_marker in str((spec_reads[0].payload.get("result") or {}).get("text", "")),
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
    if "reply" in exp:
        checks.append(Check("specialist_reply_matches", result.reply == exp["reply"],
                            f"got {result.reply!r} want {exp['reply']!r}"))
    if "handoffs" in exp:
        checks.append(Check("handoff_count_matches",
                            result.handoffs == int(exp["handoffs"]) == len(handoffs),
                            f"result={result.handoffs} events={len(handoffs)}"))
    return checks


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


def _budget_drill(task: dict) -> list:
    """The tool-call governor: a capped run stops BEFORE the rejected call.

    Honest contract: the ``budget`` event names the rejected tool, the cap is
    recorded at run_start, executed calls all precede the budget line, no reply
    is fabricated, and the scripted tail stays unconsumed (script exhaustion
    and budget exhaustion are different animals).
    """
    wd = _fresh_wd("budget")
    script = _script(task)
    cap = int(task.get("max_tool_calls", 2))
    llm = ScriptedLLM(script)
    runner = AgentRunner(
        llm, builtin_tools(wd), os.path.join(wd, "journal.jsonl"),
        max_steps=int(task.get("max_steps", 8)), max_tool_calls=cap,
        workdir=wd, run_id=str(task.get("run_id", "budget-drill")),
    )
    result = runner.run(str(task.get("task_text", "budget drill")))
    events, _torn = load_trace(os.path.join(wd, "journal.jsonl"))
    exp = _expect(task)
    budget_evts = [e for e in events if e.type == "budget"]
    b = budget_evts[0].payload if budget_evts else {}
    tool_calls = [e for e in events if e.type == "tool_call"]
    rejected = str(exp.get("rejected_tool", ""))
    return [
        Check("stop_reason_budget",
              result.stop_reason == "budget" and events[-1].type == "run_end"
              and events[-1].payload.get("stop_reason") == "budget",
              f"got {result.stop_reason}"),
        Check("budget_event_present", len(budget_evts) == 1,
              f"{len(budget_evts)} budget events"),
        Check("budget_payload_honest",
              b.get("kind") == "tool_calls" and b.get("used") == cap
              and b.get("cap") == cap and b.get("rejected_tool") == rejected,
              str(b)[:90]),
        Check("budget_precedes_run_end",
              bool(budget_evts) and budget_evts[0].seq < events[-1].seq),
        Check("rejected_tool_never_ran",
              len(tool_calls) == exp.get("tool_calls", cap)
              and all(e.seq < budget_evts[0].seq for e in tool_calls)
              and not any(e.seq > budget_evts[0].seq for e in events
                          if e.type == "tool_result"),
              f"{len(tool_calls)} calls, all before the budget line"),
        Check("cap_recorded_at_start",
              any(e.type == "run_start" and e.payload.get("max_tool_calls") == cap
                  for e in events)),
        Check("capped_attempt_counts_a_step",
              result.steps == exp.get("steps", cap + 1), f"steps={result.steps}"),
        Check("script_tail_unconsumed", llm.cursor < len(script),
              f"cursor={llm.cursor}/{len(script)} — budget, not script exhaustion"),
        Check("no_reply_fabricated", not any(e.type == "reply" for e in events)),
        Check("journal_dense_reopen",
              sequence_dense(events)
              and sequence_dense(_reopen(os.path.join(wd, "journal.jsonl")))),
    ]


def _stop_drill(task: dict) -> list:
    """The reserved stop tool: an explicit, reasoned stop — never a tool_call.

    Honest contract: ``stop`` is control-plane (reserved, unjournaled as a tool
    call, budget-free), the stop reason lands in the final ``run_end`` payload,
    prior work stays in the journal, and the scripted reply tail is never
    consumed — stopping is not replying.
    """
    wd = _fresh_wd("stop")
    script = _script(task)
    llm = ScriptedLLM(script)
    runner = AgentRunner(
        llm, builtin_tools(wd), os.path.join(wd, "journal.jsonl"),
        max_steps=int(task.get("max_steps", 8)),
        max_tool_calls=int(task.get("max_tool_calls", 0)),
        workdir=wd, run_id=str(task.get("run_id", "stop-drill")),
    )
    result = runner.run(str(task.get("task_text", "stop drill")))
    events, _torn = load_trace(os.path.join(wd, "journal.jsonl"))
    exp = _expect(task)
    run_end = events[-1]
    stop_calls = [e for e in events if e.type == "tool_call"
                  and e.payload.get("tool") == "stop"]
    results_ok = [e for e in events if e.type == "tool_result" and e.payload.get("ok")]
    exp_value = exp.get("last_result_value")
    if exp_value is None:
        prior_ok, prior_detail = True, "no value expected"
    else:
        val = (results_ok[-1].payload.get("result") or {}).get("value") if results_ok else None
        prior_ok, prior_detail = val == exp_value, f"last result value={val!r} want {exp_value!r}"
    return [
        Check("stop_reason_stop_tool",
              result.stop_reason == "stop_tool" and run_end.type == "run_end"
              and run_end.payload.get("stop_reason") == "stop_tool",
              f"got {result.stop_reason}"),
        Check("stop_reason_recorded", run_end.payload.get("reason") == exp.get("reason", ""),
              str(run_end.payload)[:80]),
        Check("stop_never_a_tool_call", not stop_calls,
              f"{len(stop_calls)} stop tool_call events"),
        Check("tool_calls_counted",
              sum(1 for e in events if e.type == "tool_call") == exp.get("tool_calls", 0)),
        Check("prior_work_preserved", prior_ok, prior_detail),
        Check("steps_match_expect", result.steps == exp.get("steps", len(script) - 1),
              f"steps={result.steps}"),
        Check("script_tail_unconsumed", llm.cursor < len(script),
              f"cursor={llm.cursor}/{len(script)} — stop fired before the reply line"),
        Check("no_reply_fabricated", not any(e.type == "reply" for e in events)),
        Check("events_end_with_run_end", run_end.type == "run_end"),
        Check("journal_dense_reopen",
              sequence_dense(events)
              and sequence_dense(_reopen(os.path.join(wd, "journal.jsonl")))),
    ]


def _redact_nested_drill(task: dict) -> list:
    """Deep redaction: ``vault_bundle`` secrets rewritten at leaves only.

    Honest contract: both credential kinds are marked, no raw token reaches the
    journal or any view, the payload keeps its shape (dict keys, list order)
    and its plain fields — redaction never mangles structure.
    """
    wd = _fresh_wd("redact_nested")
    events, result = _run_offline(task, wd)
    jp = os.path.join(wd, "journal.jsonl")
    journal_raw = open(jp, encoding="utf-8").read()
    gh, aws = vault_value("github"), vault_value("aws")
    exp = _expect(task)
    bundles = [e for e in events if e.type == "tool_result"
               and e.payload.get("tool") == "vault_bundle"]
    payload = bundles[0].payload if bundles else {}
    data = payload.get("result") or {}
    creds = data.get("creds") or []
    tview, hview = view(events, "text"), view(events, "html")
    return [
        Check("stop_reason_reply",
              result.stop_reason == exp.get("stop_reason", "reply")
              and events[-1].type == "run_end",
              f"got {result.stop_reason}"),
        Check("bundle_fetched_once",
              len(bundles) == 1 and payload.get("ok") is True
              and sum(1 for e in events if e.type == "tool_call"
                      and e.payload.get("tool") == "vault_bundle") == 1),
        Check("both_markers_in_journal",
              f"{MARKER}github_token]" in journal_raw
              and f"{MARKER}aws_key]" in journal_raw),
        Check("raw_tokens_absent", gh not in journal_raw and aws not in journal_raw),
        Check("structure_preserved",
              len(creds) == 2
              and [c.get("kind") for c in creds] == ["github", "aws"]
              and creds[0].get("token") == f"{MARKER}github_token]"
              and creds[1].get("token") == f"{MARKER}aws_key]",
              str(creds)[:90]),
        Check("plain_fields_untouched",
              (data.get("profile") or {}).get("name") == "ci-bot"
              and (data.get("profile") or {}).get("org") == "fixture"),
        Check("redaction_count_recorded",
              int(payload.get("redactions", 0) or 0) >= 2,
              f"redactions={payload.get('redactions')}"),
        Check("views_redacted_too",
              gh not in tview and aws not in tview
              and MARKER in tview and MARKER in hview
              and gh not in hview and aws not in hview),
        Check("sequence_dense", sequence_dense(events)),
        Check("journal_reopen_dense", sequence_dense(_reopen(jp))),
    ]


def _audit_drill(task: dict) -> list:
    """The repo audits itself: planted leaks found, runtime concatenation invisible.

    Honest contract: the scanner finds a literal written at runtime into a
    scratch tree (kind, file, line all correct) while redacting its own
    snippet; source-form concatenation and non-source suffixes stay invisible;
    and the repository itself always scans to 0 findings.
    """
    wd = _fresh_wd("audit")
    tok = vault_value("aws")
    with open(os.path.join(wd, "planted.py"), "w", encoding="utf-8") as fh:
        fh.write("FACTOR = 1\n" + f'key = "{tok}"\n')  # literal lands on line 2
    with open(os.path.join(wd, "clean.py"), "w", encoding="utf-8") as fh:
        fh.write('key = "AKIA" + "12AB" * 4\n')  # source-form concat: never a literal
    with open(os.path.join(wd, "skipme.bin"), "wb") as fh:
        fh.write(b"token=" + tok.encode())  # non-source suffix: never scanned
    findings1 = run_audit(wd)
    findings2 = run_audit(wd)
    exp = _expect(task)
    planted = [f for f in findings1 if f["file"] == exp.get("planted_file", "planted.py")]
    p = planted[0] if planted else {}
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_findings = run_audit(repo_root)
    return [
        Check("planted_found", len(planted) == 1, f"{len(planted)} findings"),
        Check("finding_kind_correct", p.get("kind") == exp.get("planted_kind", "aws_key"),
              str(p.get("kind"))),
        Check("finding_located", p.get("line") == exp.get("planted_line", 2),
              f"line {p.get('line')}"),
        Check("snippet_redacted",
              f"{MARKER}aws_key]" in str(p.get("snippet", "")) and tok not in str(p.get("snippet", "")),
              str(p.get("snippet", ""))[:60]),
        Check("clean_concat_invisible",
              not any(f["file"] == "clean.py" for f in findings1)),
        Check("binary_suffix_skipped",
              not any("skipme.bin" in f["file"] for f in findings1)),
        Check("findings_total_consistent", len(findings1) == 1, f"total {len(findings1)}"),
        Check("finding_shape",
              all(set(f) == {"file", "line", "kind", "snippet"} for f in findings1)),
        Check("repo_self_audit_clean", repo_findings == [],
              f"{len(repo_findings)} findings in the repository itself"),
        Check("audit_deterministic", findings1 == findings2),
    ]


def _pack_drill(task: dict) -> list:
    """Pack manifests: deterministic bytes; the verifier reports every mutation.

    Honest contract: entries carry exactly {path, bytes, sha256} (no volatile
    fields), rebuilds are byte-identical, hashes match an independent hashlib
    computation, and verify_manifest itemizes modified/extra/missing files —
    then goes green again once the tree is restored.
    """
    import hashlib as _hashlib

    from .pack import build_manifest, manifest_json, verify_manifest, write_manifest

    wd = _fresh_wd("pack")
    with open(os.path.join(wd, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("alpha payload\n")
    os.makedirs(os.path.join(wd, "sub"))
    with open(os.path.join(wd, "sub", "b.json"), "w", encoding="utf-8") as fh:
        fh.write('{"n": 1}\n')
    with open(os.path.join(wd, "notes.md"), "w", encoding="utf-8") as fh:
        fh.write("# notes\n")
    exp = _expect(task)
    m1, m2 = build_manifest(wd), build_manifest(wd)
    paths = [e["path"] for e in m1["files"]]
    a_entry = next(e for e in m1["files"] if e["path"] == "a.txt")
    a_digest = _hashlib.sha256(open(os.path.join(wd, "a.txt"), "rb").read()).hexdigest()
    written = write_manifest(wd)
    import json as _json

    reloaded = _json.loads(manifest_json(written))
    base_ok, base_problems = verify_manifest(wd, reloaded)
    # tamper: modify, then extra, then missing — each detected honestly
    with open(os.path.join(wd, "a.txt"), "a", encoding="utf-8") as fh:
        fh.write("tampered\n")
    mod_ok, mod_probs = verify_manifest(wd, written)
    with open(os.path.join(wd, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("alpha payload\n")
    with open(os.path.join(wd, "extra.txt"), "w", encoding="utf-8") as fh:
        fh.write("sneaky\n")
    extra_ok, extra_probs = verify_manifest(wd, written)
    os.remove(os.path.join(wd, "extra.txt"))
    os.remove(os.path.join(wd, "sub", "b.json"))
    miss_ok, miss_probs = verify_manifest(wd, written)
    with open(os.path.join(wd, "sub", "b.json"), "w", encoding="utf-8") as fh:
        fh.write('{"n": 1}\n')
    final_ok, final_problems = verify_manifest(wd, written)
    return [
        Check("manifest_lists_all_files",
              m1["file_count"] == exp.get("file_count", 3)
              and paths == sorted(paths) == ["a.txt", "notes.md", "sub/b.json"],
              str(paths)),
        Check("entries_canonical",
              all(set(e) == {"path", "bytes", "sha256"} for e in m1["files"])
              and set(m1) == {"algo", "root", "file_count", "tree_sha256", "files"}),
        Check("tree_hash_64hex", bool(re.fullmatch(r"[0-9a-f]{64}", m1["tree_sha256"]))),
        Check("build_is_deterministic", manifest_json(m1) == manifest_json(m2)),
        Check("hash_matches_independent_hashlib", a_entry["sha256"] == a_digest),
        Check("written_manifest_roundtrips", base_ok and base_problems == [],
              str(base_problems)),
        Check("detect_modification",
              not mod_ok and mod_probs == ["modified: a.txt"], str(mod_probs)),
        Check("detect_extra",
              not extra_ok and extra_probs == ["extra: extra.txt"], str(extra_probs)),
        Check("detect_missing",
              not miss_ok and miss_probs == ["missing: sub/b.json"], str(miss_probs)),
        Check("verify_green_after_restore", final_ok and final_problems == []),
    ]


def _sbom_drill(task: dict) -> list:
    """The BOM's purity verdict is computed, not promised.

    Honest contract: the repo BOM lists every module with an independent-shape
    entry and hashes, is stdlib-only with zero network modules, and is
    byte-reproducible; a controlled scratch package classifies imports exactly
    and one foreign import flips ``stdlib_only`` to False.
    """
    from .sbom import build_sbom, sbom_json

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    s1 = build_sbom(repo_root)
    s2 = build_sbom(repo_root)
    n_src = len([f for f in os.listdir(os.path.join(repo_root, "openagentx"))
                 if f.endswith(".py")])
    exp = _expect(task)
    mods = {m["module"]: m for m in s1["modules"]}
    # controlled scratch package: stdlib + relative + absolute-local + foreign
    wd = _fresh_wd("sbom")
    p = os.path.join(wd, exp.get("package", "openagentx") + "-scratch", "mypkg")
    os.makedirs(p)
    with open(os.path.join(p, "__init__.py"), "w", encoding="utf-8") as fh:
        fh.write("")
    with open(os.path.join(p, "alpha.py"), "w", encoding="utf-8") as fh:
        fh.write("import json\nimport os\nfrom . import beta_helper\n")
    with open(os.path.join(p, "beta.py"), "w", encoding="utf-8") as fh:
        fh.write("import mypkg.alpha\nfrom mypkg.alpha import x\n")
    scratch = build_sbom(wd, pkg_dir=p)
    by = {m["module"]: m for m in scratch["modules"]}
    alpha = by.get("mypkg.alpha", {})
    with open(os.path.join(p, "gamma.py"), "w", encoding="utf-8") as fh:
        fh.write("import not_a_real_stdlib_module\n")
    flipped = build_sbom(wd, pkg_dir=p)
    return [
        Check("repo_modules_all_listed", s1["module_count"] == n_src,
              f"{s1['module_count']} vs {n_src} source files"),
        Check("repo_every_module_hashed",
              all(re.fullmatch(r"[0-9a-f]{64}", m["sha256"]) for m in s1["modules"])),
        Check("repo_entry_shape",
              all(set(m) == {"module", "path", "sha256", "stdlib_imports",
                             "local_imports", "foreign_imports"}
                  for m in s1["modules"])),
        Check("repo_pure_stdlib", s1["stdlib_only"] is True),
        Check("repo_no_network_modules", s1["network_modules"] == []),
        Check("repo_entrypoints_covered",
              "openagentx" in mods and "openagentx.__main__" in mods),
        Check("bom_deterministic", sbom_json(s1) == sbom_json(s2)),
        Check("scratch_imports_classified",
              alpha.get("stdlib_imports") == ["json", "os"]
              and alpha.get("local_imports") == ["."]
              and by.get("mypkg.beta", {}).get("local_imports") == ["mypkg.alpha"],
              str(alpha)[:80]),
        Check("scratch_verdict_flips_on_foreign", flipped["stdlib_only"] is False),
        Check("scratch_shape_matches_repo",
              all(set(m) == set(next(iter(mods.values()))) for m in scratch["modules"])),
    ]


def _memory_drill(task: dict) -> list:
    """TF-IDF recall over past runs: right run first, redaction intact, read-only.

    Honest contract: memory indexes only what the redacted journals already
    say, ranks the run that actually talked about the query first —
    deterministically — returns nothing for an unknown query instead of a
    hallucinated hit, never writes to the journals, and never surfaces a raw
    fixture token even when a past run genuinely touched the vault.
    """
    from .memory import MemoryLite

    wd = _fresh_wd("memory")
    runs_spec = list(task.get("runs", []))
    journals = []
    for r in runs_spec:
        jp = os.path.join(wd, f"journal-{r.get('run_id', 'run')}.jsonl")
        AgentRunner(
            ScriptedLLM([str(s) for s in r.get("script", [])]),
            builtin_tools(wd), jp,
            max_steps=int(r.get("max_steps", 6)), workdir=wd,
            run_id=str(r.get("run_id", "")),
        ).run(str(r.get("task_text", "memory drill run")))
        journals.append(jp)
    before = {jp: open(jp, "rb").read() for jp in journals}
    mem = MemoryLite()
    for jp in journals:
        mem.index_journal(jp)
    queries = list(task.get("queries", []))
    checks = [Check("runs_indexed", mem.runs == len(runs_spec),
                    f"{mem.runs}/{len(runs_spec)}")]
    first_hits = []
    for i, q in enumerate(queries, 1):
        hits = mem.recall(str(q.get("q", "")), k=3)
        first_hits.append(hits)
        checks.append(Check(f"recall_{i}_top_hit",
                            bool(hits) and hits[0]["run_id"] == str(q.get("top", "")),
                            str([(h["run_id"], h["score"]) for h in hits])[:70]))
    q0 = str(queries[0].get("q", "")) if queries else ""
    checks.extend([
        Check("recall_deterministic",
              bool(first_hits) and mem.recall(q0, k=3) == first_hits[0],
              "same query, same ranking"),
        Check("k_limit_respected", len(mem.recall(q0, k=1)) == 1,
              "k=1 returns exactly one hit"),
        Check("unknown_query_empty", mem.recall("quantum widget zzzq") == [],
              "no hallucinated hits"),
    ])
    top = first_hits[0][0] if first_hits and first_hits[0] else None
    checks.append(Check(
        "snippet_lives_in_journal",
        bool(top) and str(top["snippet"]) in open(top["journal"], encoding="utf-8").read(),
        str(top)[:60] if top else "no hit"))
    checks.append(Check(
        "memory_is_read_only",
        all(open(jp, "rb").read() == before[jp] for jp in journals),
        "journals byte-identical after index+recall"))
    seen_text = "".join(open(jp, encoding="utf-8").read() for jp in journals) + str(first_hits)
    checks.append(Check("redaction_preserved", vault_value("github") not in seen_text,
                        "raw fixture token never reaches memory"))
    checks.append(Check("journals_dense_reopen",
                        all(sequence_dense(_reopen(jp)) for jp in journals)))
    return checks


def _compact_drill(task: dict) -> list:
    """Compaction: denser secondary journal, original untouched, folds honest.

    Honest contract: the source journal stays byte-identical, the compacted
    copy loads dense with every adjacent tool_call+tool_result pair folded
    into one ``tool_fold`` carrying {tool, ok, redactions}, run bounds /
    reply / thoughts survive verbatim, replay stays sane, and a second
    compaction is byte-identical.
    """
    from .compact import compact_journal

    wd = _fresh_wd("compact")
    src = os.path.join(wd, "journal.jsonl")
    events, _result = _run_offline(task, wd)
    src_before = open(src, "rb").read()
    dst1 = os.path.join(wd, "journal.compact.jsonl")
    dst2 = os.path.join(wd, "journal.compact2.jsonl")
    stats = compact_journal(src, dst1)
    compact_journal(src, dst2)
    src_after = open(src, "rb").read()
    c_events, torn = load_trace(dst1)
    pairs = []
    pending = None
    for e in events:
        if e.type == "tool_call":
            pending = str((e.payload or {}).get("tool", ""))
        elif e.type == "tool_result" and pending is not None:
            pairs.append((pending, bool((e.payload or {}).get("ok"))))
            pending = None
    folds = [e for e in c_events if e.type == "tool_fold"]
    fold_tools = [(f.payload.get("tool"), f.payload.get("ok")) for f in folds]
    src_reds = sum(int((e.payload or {}).get("redactions", 0) or 0)
                   for e in events if e.type == "tool_result")
    exp = _expect(task)
    reply_text = str(exp.get("reply", ""))
    st = replay(c_events)
    return [
        Check("original_untouched", src_after == src_before,
              "append-only invariant holds"),
        Check("compacted_loads_dense", not torn and sequence_dense(c_events),
              f"{len(c_events)} events, torn={torn}"),
        Check("smaller_event_count",
              stats["dst_events"] < stats["src_events"] and stats["ratio"] < 1.0,
              f"{stats['src_events']} -> {stats['dst_events']} (ratio {stats['ratio']})"),
        Check("stats_honest", stats["dst_events"] == len(c_events)
              and stats["tool_folds"] == len(folds),
              "reported numbers match the file"),
        Check("bookkeeping_dropped",
              not any(e.type in ("step_start", "step_end") for e in c_events)),
        Check("tool_pairs_folded",
              not any(e.type in ("tool_call", "tool_result") for e in c_events)
              and fold_tools == pairs,
              str(fold_tools)[:70]),
        Check("fold_redactions_sum",
              sum(int(f.payload.get("redactions", 0) or 0) for f in folds) == src_reds,
              f"folds={sum(int(f.payload.get('redactions', 0) or 0) for f in folds)} src={src_reds}"),
        Check("run_bounds_preserved",
              c_events[0].type == "run_start" and c_events[-1].type == "run_end"
              and c_events[-1].payload.get("stop_reason") == exp.get("stop_reason", "reply"),
              str(c_events[-1].payload)[:60]),
        Check("reply_text_preserved",
              any(e.type == "reply" and e.payload.get("text") == reply_text
                  for e in c_events), reply_text[:50]),
        Check("thoughts_kept",
              sum(1 for e in events if e.type == "thought")
              == sum(1 for e in c_events if e.type == "thought"),
              "the reasoning narrative survives"),
        Check("compaction_deterministic",
              open(dst1, "rb").read() == open(dst2, "rb").read(),
              "byte-identical re-compaction"),
        Check("replay_compacted_sane",
              st["runs_opened"] == 1 and st["replies"] == 1
              and st["final_stop"] == exp.get("stop_reason", "reply"),
              str(st)[:80]),
        Check("view_renders_compacted", reply_text in view(c_events, "text"),
              "views work on the folded stream"),
    ]


def _cache_drill(task: dict) -> list:
    """Prompt-hash cache: exact repeats come from the store, never invented.

    Honest contract: a hit serves the very turn stored for that exact prompt
    (the inner adapter is not called), keys are canonical and order-sensitive,
    counters match observed behavior, mutation of a returned turn cannot
    poison the store, and a replayed run journals the same event shape as the
    computed one — the cache is invisible to the journal, by design.
    """
    from .cache import CachedLLM, ResponseCache, prompt_key

    wd = _fresh_wd("cache")
    exp = _expect(task)
    reply = str(exp.get("reply", "cached answer"))
    # 1) adapter-level probes on a dedicated tiny inner script
    inner = ScriptedLLM(['{"reply": "' + reply.replace('"', '\\"') + '"}',
                         '{"reply": "computed for another prompt"}'])
    cache = ResponseCache()
    cached = CachedLLM(inner, cache)
    msgs = [{"role": "user", "content": "compute 6*7"}]
    t1 = cached.complete(msgs)
    inner_calls_after_hit = inner.calls  # t2 must NOT call the inner adapter
    t2 = cached.complete(msgs)
    t3 = cached.complete([{"role": "user", "content": "another prompt"}])
    hit_equals_stored = (t1 == t2 == {"reply": reply})  # captured BEFORE the mutation probe
    t2["reply"] = "POISON-ATTEMPT"
    t4 = cached.complete(msgs)
    key_checks = (
        prompt_key(msgs) == prompt_key([{"role": "user", "content": "compute 6*7"}])
        and prompt_key(msgs) != prompt_key([{"role": "user", "content": "compute 6*8"}])
        and prompt_key(msgs) != prompt_key(msgs + [{"role": "user", "content": "OBS"}])
    )
    # 2) runner-level: the same task run twice through one shared cache
    script = _script(task)
    shared = ResponseCache()
    results, type_seqs, inners = [], [], []
    for i, name in enumerate(("first", "again")):
        inner_i = ScriptedLLM(list(script))
        inners.append(inner_i)
        jp = os.path.join(wd, f"journal-{name}.jsonl")
        results.append(AgentRunner(
            CachedLLM(inner_i, shared), builtin_tools(wd), jp,
            max_steps=int(task.get("max_steps", 6)), workdir=wd,
            run_id=f"cache-drill-{i}").run(str(task.get("task_text", "cached drill"))))
        events, _torn = load_trace(jp)
        type_seqs.append([e.type for e in events])
    st = shared.stats()
    return [
        Check("adapter_hit_serves_same_turn",
              hit_equals_stored and inner_calls_after_hit == 1,
              f"hit==stored={hit_equals_stored}, "
              f"inner calls right after the repeat lookup={inner_calls_after_hit}"),
        Check("adapter_miss_for_new_prompt",
              t3 == {"reply": "computed for another prompt"} and inner.calls == 2),
        Check("mutation_cannot_poison", t4["reply"] == reply,
              f"after mutating a returned hit: {t4['reply']!r}"),
        Check("keys_canonical_order_sensitive", key_checks,
              "same msgs same key; content/order changes change the key"),
        Check("counters_honest",
              st == {"hits": 2, "misses": 2, "size": 2} and cached.calls == 2,
              str(st)),
        Check("runner_reply_matches",
              results[0].stop_reason == "reply" and results[0].reply == reply,
              f"got {results[0].reply!r}"),
        Check("second_run_served_from_cache",
              results[1].reply == results[0].reply and shared.hits >= 1
              and shared.misses >= 2,
              f"hits={shared.hits} misses={shared.misses}"),
        Check("inner_calls_saved",
              sum(c.calls for c in inners) == len(script)
              and len(inners) * len(script) == 2 * len(script),
              f"{len(inners) * len(script)} turns served, "
              f"{sum(c.calls for c in inners)} reached an inner adapter"),
        Check("cached_journal_shape_identical", type_seqs[0] == type_seqs[1],
              "a cached run journals exactly like a computed one"),
        Check("journals_dense_reopen",
              all(sequence_dense(_reopen(os.path.join(wd, f"journal-{n}.jsonl")))
                  for n in ("first", "again"))),
    ]


def _hooks_drill(task: dict) -> list:
    """Hook policy: denied calls never execute; every decision is journaled.

    Honest contract: the deny rule fires before the registry (no tool_call /
    tool_result for the denied tool), decisions land as ``hook`` events with
    an exact payload, the first matching rule wins, the denied attempt costs
    a step, the agent observes the denial and still finishes, and a run
    without a policy journals zero hook events.
    """
    wd = _fresh_wd("hooks")
    from .hooks import HookPolicy

    exp = _expect(task)
    rules = [dict(r) for r in (task.get("hooks") or {}).get("rules", [])]
    policy = HookPolicy(rules)
    script = _script(task)
    runner = AgentRunner(
        ScriptedLLM(list(script)), builtin_tools(wd),
        os.path.join(wd, "journal.jsonl"),
        max_steps=int(task.get("max_steps", 6)), workdir=wd,
        run_id="hooks-drill", hooks=policy,
    )
    result = runner.run(str(task.get("task_text", "hooks drill")))
    events, _torn = load_trace(os.path.join(wd, "journal.jsonl"))
    hooks = [e for e in events if e.type == "hook"]
    denied = [h for h in hooks if h.payload.get("decision") == "deny"]
    allowed = [h for h in hooks if h.payload.get("decision") == "allow"]
    tool_calls = [e for e in events if e.type == "tool_call"]
    tool_results = [e for e in events if e.type == "tool_result"]
    replies = [e for e in events if e.type == "reply"]
    denied_tool = str(exp.get("denied_tool", ""))
    # baseline: identical script, no policy -> zero hook events
    wd2 = os.path.join(wd, "baseline")
    os.makedirs(wd2, exist_ok=True)
    base_runner = AgentRunner(
        ScriptedLLM(list(script)), builtin_tools(wd2),
        os.path.join(wd2, "journal.jsonl"),
        max_steps=int(task.get("max_steps", 6)), workdir=wd2, run_id="hooks-base",
    )
    base_result = base_runner.run(str(task.get("task_text", "hooks drill")))
    base_events, _t2 = load_trace(os.path.join(wd2, "journal.jsonl"))
    return [
        Check("deny_event_present",
              len(denied) == 1 and denied[0].payload.get("tool") == denied_tool,
              str([h.payload for h in denied])[:80]),
        Check("first_match_wins",
              denied[0].payload.get("reason") == str(exp.get("deny_reason", ""))
              if denied else False, "reason comes from the first matching rule"),
        Check("allow_decisions_journaled",
              len(allowed) == len(tool_calls)
              and all(a.payload.get("tool") == t.payload.get("tool")
                      for a, t in zip(allowed, tool_calls)),
              f"{len(allowed)} allow events for {len(tool_calls)} calls"),
        Check("denied_tool_never_executed",
              not any(e.payload.get("tool") == denied_tool
                      for e in tool_calls + tool_results),
              "no tool_call, no tool_result, no side effects"),
        Check("hook_payload_shape",
              all(set(h.payload) == {"tool", "decision", "reason"} for h in hooks),
              "control-plane facts only"),
        Check("agent_observes_denial_and_adapts",
              result.stop_reason == "reply" and bool(replies)
              and (not denied or replies[0].seq > denied[0].seq),
              f"stop={result.stop_reason}"),
        Check("denied_attempt_counts_a_step",
              result.steps == exp.get("steps", len(script)),
              f"steps={result.steps}"),
        Check("executed_tools_recorded",
              len(tool_calls) == int(exp.get("allowed_tools", len(tool_calls))),
              f"{len(tool_calls)} executed calls"),
        Check("baseline_without_policy_clean",
              base_result.stop_reason == "reply"
              and not any(e.type == "hook" for e in base_events),
              "no policy -> no hook events, run unaffected"),
        Check("run_bounds_preserved",
              events[0].type == "run_start" and events[-1].type == "run_end"
              and events[-1].payload.get("stop_reason") == "reply"),
        Check("journal_dense_reopen",
              sequence_dense(events)
              and sequence_dense(_reopen(os.path.join(wd, "journal.jsonl")))),
    ]


def _fanout_drill(task: dict) -> list:
    """Parallel fan-out: real branch runs, honest failure data, ordered fan-in.

    Honest contract: every branch is a real AgentRunner run with its own
    dense journal; the parent references children by name and run_id; a
    failing branch is recorded (``script_error`` + empty reply) instead of
    poisoning the run; dispatch order follows spec order; the coordinator
    answers only from the fanin; a re-run with fixed run_ids is structurally
    identical (same seq/run_id/type/payload stream, wall-clock excluded).
    """
    from .fanout import FanoutRunner, fanout_fingerprint

    wd = _fresh_wd("fanout")
    exp = _expect(task)
    branches_spec = dict(task.get("branches", {}))
    coord_script = [str(s) for s in task.get("coordinator_script", [])]
    parent = os.path.join(wd, "journal.jsonl")
    runner = FanoutRunner(
        ScriptedLLM(coord_script, name="coordinator"),
        {n: ScriptedLLM([str(s) for s in b.get("script", [])], name=str(n))
         for n, b in branches_spec.items()},
        builtin_tools(wd), parent,
        workdir=wd, run_id="fanout-drill",
        max_steps_per_branch=int(task.get("max_steps_per_branch", 6)),
        branch_tasks={n: str(b.get("task_text", "")) for n, b in branches_spec.items()},
    )
    result = runner.run(str(task.get("task_text", "fanout drill")))
    events, torn = load_trace(parent)
    branch_starts = [e for e in events if e.type == "branch_start"]
    branch_ends = {str(e.payload.get("branch")): e
                   for e in events if e.type == "branch_end"}
    fanins = [e for e in events if e.type == "fanin"]
    failed = str(exp.get("failed_branch", ""))
    replies_map = {b.name: b.reply for b in result.branches}
    stop_map = {b.name: b.stop_reason for b in result.branches}
    tools_count = {b.name: sum(1 for e in _reopen(b.journal_path) if e.type == "tool_call")
                   for b in result.branches}
    # determinism: same fixed run_ids in a fresh directory
    rerun_wd = os.path.join(wd, "rerun")
    os.makedirs(rerun_wd, exist_ok=True)
    FanoutRunner(
        ScriptedLLM(coord_script, name="coordinator"),
        {n: ScriptedLLM([str(s) for s in b.get("script", [])])
         for n, b in branches_spec.items()},
        builtin_tools(rerun_wd), os.path.join(rerun_wd, "journal.jsonl"),
        workdir=rerun_wd, run_id="fanout-drill",
        max_steps_per_branch=int(task.get("max_steps_per_branch", 6)),
        branch_tasks={n: str(b.get("task_text", "")) for n, b in branches_spec.items()},
    ).run(str(task.get("task_text", "fanout drill")))
    rerun_events, _t2 = load_trace(os.path.join(rerun_wd, "journal.jsonl"))
    same_parent = fanout_fingerprint(events) == fanout_fingerprint(rerun_events)
    same_branches = all(
        fanout_fingerprint(_reopen(b.journal_path))
        == fanout_fingerprint(_reopen(os.path.join(
            rerun_wd, os.path.basename(b.journal_path))))
        for b in result.branches)
    refs_ok = all(
        branch_ends[b.name].payload.get("run_id") == b.run_id
        and _reopen(b.journal_path)[0].run_id == b.run_id
        for b in result.branches)
    outcomes_ok = (
        all(b.stop_reason == "reply" for b in result.branches)
        if not failed
        else failed in stop_map and stop_map[failed] == "script_error")
    replies_ok = all(
        next((b.reply for b in result.branches if b.name == n), None) == want
        for n, want in dict(exp.get("branch_replies", {})).items())
    coord_replies = [e for e in events if e.type == "reply"]
    return [
        Check("run_bounds_present",
              bool(events) and events[0].type == "run_start"
              and events[-1].type == "run_end"
              and events[-1].payload.get("stop_reason")
              == exp.get("stop_reason", "reply"),
              f"last={events[-1].type if events else 'none'}"),
        Check("journal_dense", not torn and sequence_dense(events),
              f"{len(events)} events, torn={torn}"),
        Check("branch_count_matches", len(result.branches) == len(branches_spec),
              f"{len(result.branches)}/{len(branches_spec)}"),
        Check("dispatch_order_matches",
              [b.name for b in result.branches] == list(branches_spec.keys())
              and [str(e.payload.get("branch")) for e in branch_starts]
              == list(branches_spec.keys()),
              str([b.name for b in result.branches])),
        Check("branch_replies_match", replies_ok, str(replies_map)[:70]),
        Check("branch_tools_executed",
              all(tools_count[b.name] == int(dict(exp.get("branch_tools", {})).get(b.name, 0))
                  for b in result.branches),
              str(tools_count)),
        Check("branch_outcomes_match_spec", outcomes_ok, str(stop_map)),
        Check("failed_branch_reply_empty",
              (not failed) or (replies_map.get(failed) == ""
                               and stop_map.get(failed) == "script_error"),
              f"failed={failed!r} reply={replies_map.get(failed)!r}"),
        Check("branch_journals_dense",
              all(sequence_dense(_reopen(b.journal_path)) for b in result.branches)),
        Check("branch_journals_reopen_dense",
              all(sequence_dense(_reopen(os.path.join(
                  rerun_wd, os.path.basename(b.journal_path))))
                  for b in result.branches)),
        Check("parent_references_children", refs_ok,
              str({b.name: b.run_id for b in result.branches})[:70]),
        Check("fanin_event_present",
              len(fanins) == 1
              and fanins[0].payload.get("branches") == len(branches_spec)
              and fanins[0].payload.get("replies") == replies_map
              and fanins[0].payload.get("stop_reasons") == stop_map,
              str(fanins[0].payload)[:70] if fanins else "missing fanin"),
        Check("coordinator_reply_matches",
              result.stop_reason == "reply" and result.reply == exp.get("reply", "")
              and bool(coord_replies)
              and (coord_replies[-1].payload or {}).get("role") == "coordinator",
              f"reply={result.reply!r}"),
        Check("structural_determinism", same_parent and same_branches,
              f"parent={same_parent} branches={same_branches}"),
    ]


def _structured_drill(task: dict) -> list:
    """Structured output: messy JSON repaired with honest notes, validated.

    Honest contract: the runner's real reply is repaired with an exact note
    list, every spec case parses to exactly its expected value (and notes),
    hopeless input raises ``ValueError`` loudly instead of inventing a value,
    parsing is deterministic, and the lite schema catches missing required
    keys, wrong types and ``True`` masquerading as an integer.
    """
    from .structured import parse_json_loose, validate_schema

    wd = _fresh_wd("structured")
    exp = _expect(task)
    events, result = _run_offline(task, wd)
    replies = [e for e in events if e.type == "reply"]
    reply_text = str(replies[-1].payload.get("text", "")) if replies else ""
    schema = task.get("schema", {})
    cases = list(task.get("cases", []))
    value, notes = parse_json_loose(reply_text)
    checks = [
        Check("runner_reply_parses",
              result.stop_reason == "reply"
              and value == exp.get("value")
              and notes == list(exp.get("notes", [])),
              f"value={value} notes={notes}"),
        Check("schema_validates_value", validate_schema(value, schema) == [],
              str(validate_schema(value, schema))[:70]),
    ]
    for i, case in enumerate(cases, 1):
        text = str(case.get("text", ""))
        if case.get("error"):
            try:
                parse_json_loose(text)
                checks.append(Check(f"case_{i}", False, "no raise on hopeless input"))
            except ValueError as e:
                checks.append(Check(f"case_{i}",
                                    str(e).startswith(str(case.get("error", "unparseable JSON"))),
                                    str(e)[:60]))
        else:
            try:
                v, n = parse_json_loose(text)
                ok = v == case.get("want") and ("notes" not in case or n == list(case["notes"]))
            except ValueError:
                ok = False
            checks.append(Check(f"case_{i}", ok, f"case {i}: {text[:40]!r}"))
    first = str(cases[0].get("text", "")) if cases else ""
    checks.extend([
        Check("parse_deterministic",
              bool(first) and parse_json_loose(first) == parse_json_loose(first),
              "same input, same value and notes"),
        Check("schema_missing_required_detected",
              any("missing required" in err
                  for err in validate_schema(exp.get("missing_required", {}), schema)),
              str(validate_schema(exp.get("missing_required", {}), schema))[:70]),
        Check("schema_type_mismatch_detected",
              any("want" in err
                  for err in validate_schema(exp.get("type_mismatch", {}), schema)),
              str(validate_schema(exp.get("type_mismatch", {}), schema))[:70]),
        Check("schema_bool_not_integer",
              any("got bool" in err
                  for err in validate_schema(exp.get("bool_not_integer", {}), schema)),
              "True must never satisfy integer"),
    ])
    return checks


def _retry_drill(task: dict) -> list:
    """Retry with backoff: transient faults recovered on a fixed schedule.

    Honest contract: every attempt is logged (outcome, error, delay), the
    recovery path shows its scars, give-up raises a loud ``RetryExhausted``
    that names the attempt count, non-retryable plan bugs propagate
    immediately instead of being laundered, the backoff schedule is exactly
    what the policy advertises, and a retried run journals exactly like a
    healthy one — retries never touch the journal.
    """
    from .llm import LLMUnavailable, ScriptExhausted
    from .retry import BackoffPolicy, RetryExhausted, RetryLLM

    wd = _fresh_wd("retry")
    exp = _expect(task)
    script = _script(task)
    fail_first = int(exp.get("fail_first", 1))
    max_attempts = int(exp.get("max_attempts", 3))
    base_delay = float(exp.get("base_delay", 0.0))
    factor = float(exp.get("factor", 2.0))

    class FlakyLLM:
        """Fault double: fails the first *fail_first* calls, then serves."""

        def __init__(self, script, fail_first):
            self.inner = ScriptedLLM(script)
            self.fail_first = int(fail_first)
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            if self.calls <= self.fail_first:
                raise LLMUnavailable(f"transient outage (call {self.calls})")
            return self.inner.complete(messages)

    schedule = BackoffPolicy(max_attempts, base_delay, factor).delays()
    want_schedule = [round(base_delay * (factor ** i), 6)
                     for i in range(max_attempts - 1)]

    flaky = FlakyLLM(['{"reply": "ok"}'], fail_first=2)
    adapter = RetryLLM(flaky, BackoffPolicy(max_attempts=4, base_delay=0.001,
                                            factor=2.0))
    turn = adapter.complete([{"role": "user", "content": "hi"}])
    ok_flags = [a["ok"] for a in adapter.attempts]
    delays_seen = [a["delay"] for a in adapter.attempts]

    giveup = RetryLLM(FlakyLLM(['{"reply": "x"}'], 99),
                      BackoffPolicy(max_attempts=3))
    gave_up_error = ""
    try:
        giveup.complete([])
    except RetryExhausted as e:
        gave_up_error = str(e)

    planbug = RetryLLM(FlakyLLM([], 0), BackoffPolicy(max_attempts=5))
    bug_type = "unraised"
    try:
        planbug.complete([])
    except RetryExhausted:
        bug_type = "wrapped"
    except ScriptExhausted:
        bug_type = "propagated"

    flaky_run = FlakyLLM(list(script), fail_first)
    jp = os.path.join(wd, "journal.jsonl")
    result = AgentRunner(
        RetryLLM(flaky_run, BackoffPolicy(max_attempts=max_attempts,
                                          base_delay=base_delay, factor=factor)),
        builtin_tools(wd), jp, max_steps=int(task.get("max_steps", 8)),
        workdir=wd, run_id="retry-drill").run(str(task.get("task_text", "retry drill")))
    events, torn = load_trace(jp)
    healthy_jp = os.path.join(wd, "healthy.jsonl")
    AgentRunner(ScriptedLLM(list(script)), builtin_tools(wd), healthy_jp,
                max_steps=int(task.get("max_steps", 8)), workdir=wd,
                run_id="retry-healthy").run(str(task.get("task_text", "retry drill")))
    healthy_events, _t2 = load_trace(healthy_jp)
    return [
        Check("backoff_schedule_deterministic", schedule == want_schedule,
              f"{schedule} vs {want_schedule}"),
        Check("recovers_after_transient",
              turn == {"reply": "ok"} and ok_flags == [False, False, True],
              f"attempts ok={ok_flags}"),
        Check("delays_follow_schedule", delays_seen == [0.001, 0.002, 0.0],
              str(delays_seen)),
        Check("give_up_is_loud", "gave up after 3 attempts" in gave_up_error,
              gave_up_error[:70]),
        Check("give_up_attempts_honest",
              len(giveup.attempts) == 3
              and not any(a["ok"] for a in giveup.attempts),
              f"{len(giveup.attempts)} attempts, all failed"),
        Check("non_retryable_propagates", bug_type == "propagated",
              "ScriptExhausted is a plan bug, never retried"),
        Check("retry_exhausted_is_llm_unavailable",
              issubclass(RetryExhausted, LLMUnavailable),
              "runners journal an honest stop, never a crash"),
        Check("runner_reply_matches",
              result.stop_reason == "reply" and result.reply == exp.get("reply", ""),
              f"{result.stop_reason} {result.reply!r}"),
        Check("runner_inner_calls_honest",
              flaky_run.calls == fail_first + len(script),
              f"inner calls={flaky_run.calls} want={fail_first + len(script)}"),
        Check("retries_invisible_to_journal",
              [e.type for e in events] == [e.type for e in healthy_events],
              "same event-type stream as a healthy run"),
        Check("zero_base_never_sleeps",
              BackoffPolicy(max_attempts=4).delays() == [0.0, 0.0, 0.0],
              "offline-fast contract"),
        Check("journal_dense_reopen",
              not torn and sequence_dense(events) and sequence_dense(_reopen(jp))),
    ]


def _breaker_drill(task: dict) -> list:
    """Circuit breaker: trip on real failures, fast-fail, probe to recover.

    Honest contract: the tripping failure still surfaces the *original*
    fault, open-state calls are rejected without consulting the inner
    adapter, exactly ``cooldown_calls`` rejections precede one probe, a
    failed probe re-opens and a successful one closes with an honest
    snapshot, and a runner behind an open circuit stops
    ``model_unavailable`` with zero fabricated reply text.
    """
    from .llm import LLMUnavailable
    from .breaker import CircuitBreaker, CircuitOpen

    wd = _fresh_wd("breaker")
    exp = _expect(task)
    threshold = int(exp.get("threshold", 3))
    cooldown = int(exp.get("cooldown", 2))

    class DownLLM:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            raise LLMUnavailable("dependency down")

    class DownThenGoodLLM:
        def __init__(self, fail_first, script):
            self.inner = ScriptedLLM(script)
            self.fail_first = int(fail_first)
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            if self.calls <= self.fail_first:
                raise LLMUnavailable("down")
            return self.inner.complete(messages)

    inner = ScriptedLLM(['{"reply": "a"}', '{"reply": "b"}'])
    cb0 = CircuitBreaker(inner, threshold=threshold, cooldown_calls=cooldown)
    r1 = cb0.complete([])
    r2 = cb0.complete([])

    d1 = DownLLM()
    cb1 = CircuitBreaker(d1, threshold=threshold, cooldown_calls=cooldown)
    failure_types = []
    for _ in range(threshold):
        try:
            cb1.complete([])
        except CircuitOpen:
            failure_types.append("circuit_open")
        except LLMUnavailable:
            failure_types.append("original")
    trip_state = dict(cb1.snapshot())  # state AT trip time (probe may reopen later)
    trip_calls = d1.calls
    d1_before = d1.calls
    ff_error = ""
    try:
        cb1.complete([])
    except CircuitOpen as e:
        ff_error = str(e)
    ff_calls = d1.calls  # captured now: a rejection must not consult the inner
    extra_rejections = 0
    for _ in range(cooldown - 1):
        try:
            cb1.complete([])
            extra_rejections += 0  # reaching here means no rejection: lie
        except CircuitOpen:
            extra_rejections += 1
    probe_error_type = "unraised"
    try:
        cb1.complete([])
    except CircuitOpen:
        probe_error_type = "circuit_open"
    except LLMUnavailable:
        probe_error_type = "original"

    dtg = DownThenGoodLLM(1, ['{"reply": "back"}'])
    cb2 = CircuitBreaker(dtg, threshold=1, cooldown_calls=1)
    try:
        cb2.complete([])
    except LLMUnavailable:
        pass
    try:
        cb2.complete([])
    except CircuitOpen:
        pass
    probe_reply = ""
    try:
        probe_reply = cb2.complete([]).get("reply", "")
    except LLMUnavailable:
        probe_reply = ""

    d3 = DownLLM()
    jp = os.path.join(wd, "journal.jsonl")
    result = AgentRunner(
        CircuitBreaker(d3, threshold=threshold, cooldown_calls=cooldown),
        builtin_tools(wd), jp, max_steps=int(task.get("max_steps", 8)),
        workdir=wd, run_id="breaker-drill").run(str(task.get("task_text", "breaker drill")))
    events, torn = load_trace(jp)
    raw_journal = open(jp, encoding="utf-8").read()
    error_events = [e for e in events if e.type == "error"]
    reply_events = [e for e in events if e.type == "reply"]
    script_reply = str(exp.get("script_reply", ""))
    return [
        Check("closed_passes_through",
              r1 == {"reply": "a"} and r2 == {"reply": "b"}
              and cb0.snapshot()["successes"] == 2,
              "healthy inner flows through untouched"),
        Check("snapshot_honest",
              cb0.snapshot() == {"state": "closed", "failures": 0,
                                 "successes": 2, "rejections": 0,
                                 "opens": 0, "probes": 0},
              str(cb0.snapshot())),
        Check("threshold_trips",
              trip_state["state"] == "open" and trip_state["opens"] == 1
              and trip_calls == threshold,
              f"at trip: opens={trip_state['opens']} inner calls={trip_calls}"),
        Check("tripping_failure_surfaced",
              failure_types == ["original"] * threshold,
              "every failure raised the original error, never a breaker artifact"),
        Check("open_fast_fails_without_inner",
              ff_error.startswith("circuit") and ff_calls == d1_before,
              f"inner calls {d1_before} -> {ff_calls}"),
        Check("cooldown_rejections_exact",
              cb1.snapshot()["rejections"] == cooldown
              and extra_rejections == cooldown - 1,
              f"{cb1.snapshot()['rejections']} rejections before the probe"),
        Check("probe_failure_reopens",
              cb1.state == "open" and cb1.opens == 2 and cb1.probes == 1
              and probe_error_type == "original"
              and d1.calls == threshold + 1,
              f"opens={cb1.opens} probes={cb1.probes} probe={probe_error_type}"),
        Check("probe_success_closes",
              probe_reply == "back" and cb2.state == "closed"
              and cb2.snapshot()["probes"] == 1,
              f"reply={probe_reply!r} state={cb2.state}"),
        Check("runner_stops_model_unavailable",
              result.stop_reason == exp.get("stop_reason", "model_unavailable"),
              f"stop={result.stop_reason}"),
        Check("no_fabricated_reply",
              result.reply == "" and not reply_events
              and (not script_reply or script_reply not in raw_journal),
              "the scripted reply text never reaches the journal"),
        Check("error_event_journaled",
              len(error_events) == 1 and d3.calls == 1
              and "LLMUnavailable" in str(error_events[0].payload.get("error", ""))
              if error_events else False,
              "one honest error event; the runner stops at the first "
              "model_unavailable"),
        Check("journal_dense_reopen",
              not torn and sequence_dense(events) and sequence_dense(_reopen(jp))),
    ]


def _planner_drill(task: dict) -> list:
    """Planner-executor: one plan turn, N real executor runs, one journal.

    Honest contract: the fenced plan is repaired with exact notes and
    schema-validated before anything executes, plan bugs (unparseable,
    schema-invalid, over-cap) journal an error and stop ``script_error``
    instead of being laundered into empty plans, every step is a real
    sub-agent run on its own dense journal whose ``run_id`` the parent
    records, a failing step is data (``script_error`` + empty reply) that
    never aborts the plan, and a re-run with fixed run_ids is structurally
    identical.
    """
    from .fanout import fanout_fingerprint
    from .planner import PLAN_SCHEMA, PlannerExecutor
    from .structured import validate_schema

    wd = _fresh_wd("planner")
    exp = _expect(task)
    planner_script = [str(s) for s in task.get("planner_script", [])]
    step_scripts = [[str(t) for t in ss] for ss in task.get("step_scripts", [])]
    jp = os.path.join(wd, "journal.jsonl")

    r = PlannerExecutor(
        ScriptedLLM(planner_script),
        [ScriptedLLM(ss) for ss in step_scripts],
        builtin_tools(wd), jp, workdir=wd, run_id="planner-drill",
        max_steps_per_step=int(task.get("max_steps_per_step", 6)),
    ).run(str(task.get("task_text", "planner drill")))
    events, torn = load_trace(jp)
    types = [e.type for e in events]
    plan_events = [e for e in events if e.type == "plan"]
    step_starts = [e for e in events if e.type == "step_start"]
    step_ends = [e for e in events if e.type == "step_end"]
    plan_done = [e for e in events if e.type == "plan_done"]

    # step journals: dense, parent-referenced, honest tool counts
    journal_of = {e.payload.get("index"): e.payload.get("journal", "")
                  for e in step_starts}
    child_infos = []
    for se in step_ends:
        sjp = os.path.join(wd, str(journal_of.get(se.payload.get("index"), "")))
        ce, ct = load_trace(sjp) if sjp and os.path.exists(sjp) else ([], False)
        child_infos.append((se, ce, ct))

    def child_tools(i):
        if i >= len(child_infos):
            return -1
        return sum(1 for e in child_infos[i][1] if e.type == "tool_call")

    # plan bugs: schema-invalid and over-cap plans are rejected loudly
    bug_wd = _fresh_wd("planner-bug")
    bad = PlannerExecutor(
        ScriptedLLM(['{"reply": "{\\"steps\\": \\"not-a-list\\"}"}']),
        [], builtin_tools(bug_wd), os.path.join(bug_wd, "j.jsonl"),
        workdir=bug_wd, run_id="bug-schema").run("t")
    big = {"steps": [f"s{i}" for i in range(9)]}
    cap_wd = _fresh_wd("planner-cap")
    capped = PlannerExecutor(
        ScriptedLLM(['{"reply": ' + json.dumps(json.dumps(big)) + '}']),
        [], builtin_tools(cap_wd), os.path.join(cap_wd, "j.jsonl"),
        workdir=cap_wd, run_id="bug-cap", max_plan_steps=8).run("t")

    # structural determinism: fresh dir, fixed run_id, identical stream
    wd2 = os.path.join(wd, "rerun")
    os.makedirs(wd2, exist_ok=True)
    r2 = PlannerExecutor(
        ScriptedLLM(list(planner_script)),
        [ScriptedLLM(list(ss)) for ss in step_scripts],
        builtin_tools(wd2), os.path.join(wd2, "journal.jsonl"),
        workdir=wd2, run_id="planner-drill",
        max_steps_per_step=int(task.get("max_steps_per_step", 6)),
    ).run(str(task.get("task_text", "planner drill")))
    ev2, _t2 = load_trace(os.path.join(wd2, "journal.jsonl"))

    failed = exp.get("failed_step")
    failed_end = (step_ends[failed].payload
                  if isinstance(failed, int) and failed < len(step_ends) else {})
    want_replies = exp.get("step_replies", {})
    want_tools = exp.get("step_tools", {})
    return [
        Check("run_bounds_present",
              types[0] == "run_start"
              and events[0].payload.get("mode") == "planner"
              and types[-1] == "run_end"
              and r.stop_reason == "reply",
              f"{types[0]}..{types[-1]} stop={r.stop_reason}"),
        Check("journal_dense", not torn and sequence_dense(events),
              f"{len(events)} events, torn={torn}"),
        Check("plan_event_matches",
              len(plan_events) == 1
              and plan_events[0].payload.get("steps") == exp.get("plan")
              and plan_events[0].payload.get("notes") == exp.get("plan_notes"),
              f"steps={plan_events[0].payload.get('steps') if plan_events else None} "
              f"notes={plan_events[0].payload.get('notes') if plan_events else None}"),
        Check("plan_schema_enforced_here",
              validate_schema({"steps": ["a", 1]}, PLAN_SCHEMA) != []
              and validate_schema({"steps": ["a"]}, PLAN_SCHEMA) == [],
              "lite schema rejects non-string items, accepts strings"),
        Check("plan_bugs_rejected",
              bad.stop_reason == "script_error" and bad.plan == []
              and capped.stop_reason == "script_error" and capped.plan == [],
              f"schema-bug stop={bad.stop_reason}, over-cap stop={capped.stop_reason}"),
        Check("step_count_matches",
              len(step_starts) == len(exp.get("plan", []))
              and len(step_ends) == len(exp.get("plan", [])),
              f"{len(step_starts)} starts / {len(step_ends)} ends"),
        Check("step_replies_match",
              all(str(se.payload.get("reply", "")) == want_replies[str(se.payload.get("index"))]
                  for se in step_ends if str(se.payload.get("index")) in want_replies),
              str([(se.payload.get("index"), se.payload.get("reply")) for se in step_ends])),
        Check("failed_step_reply_empty",
              failed_end.get("stop_reason") == "script_error"
              and failed_end.get("reply") == "",
              f"step {failed}: {failed_end.get('stop_reason')} reply={failed_end.get('reply')!r}"),
        Check("step_journals_dense",
              all(not ct and sequence_dense(ce) for _se, ce, ct in child_infos),
              f"{len(child_infos)} child journals"),
        Check("parent_references_children",
              all(ce and ce[0].type == "run_start"
                  and se.payload.get("run_id") == ce[0].run_id
                  for se, ce, _ct in child_infos),
              "parent step_end run_id equals the child journal's own run_id"),
        Check("step_tools_executed",
              all(child_tools(int(k)) == v for k, v in want_tools.items()),
              str([(i, child_tools(i)) for i in range(len(child_infos))])),
        Check("plan_done_event_present",
              len(plan_done) == 1
              and plan_done[0].payload.get("steps") == len(exp.get("plan", []))
              and plan_done[0].payload.get("stop_reasons")
              == [se.payload.get("stop_reason") for se in step_ends],
              str(plan_done[0].payload if plan_done else None)),
        Check("final_reply_matches",
              r.stop_reason == "reply" and r.reply == exp.get("reply", ""),
              f"{r.stop_reason} {r.reply!r}"),
        Check("structural_determinism",
              r2.stop_reason == "reply" and r2.reply == r.reply
              and fanout_fingerprint(events) == fanout_fingerprint(ev2),
              "re-run in a fresh dir: same seq/type/payload stream"),
    ]


def _snapshot_drill(task: dict) -> list:
    """Snapshot travel: checkpoints are pure prefix folds of the journal.

    Honest contract: the final checkpoint equals the full replay, earlier
    checkpoints are untouched by later events (a longer run that shares the
    prefix folds identically) and by a torn tail, travel is deterministic
    and monotone, bounds/order/density violations raise loudly instead of
    clamping, the empty journal exposes exactly the zero state, and a
    reopened journal travels identically.
    """
    from .snapshot import ZERO_STATE, monotone, snapshot_at, travel

    wd = _fresh_wd("snapshot")
    exp = _expect(task)
    jp = os.path.join(wd, "journal.jsonl")
    result = AgentRunner(
        ScriptedLLM(_script(task)), builtin_tools(wd), jp,
        max_steps=int(task.get("max_steps", 8)),
        workdir=wd, run_id="snapshot-drill").run(str(task.get("task_text", "snapshot drill")))
    events, torn = load_trace(jp)
    end = events[-1].seq if events else 0
    checkpoints = [int(c) for c in exp.get("checkpoints", [])]
    states = travel(events, checkpoints)
    again = travel(events, checkpoints)

    # longer run sharing the prefix: appending real events cannot rewrite
    # an earlier checkpoint
    wd_b = _fresh_wd("snapshot-long")
    AgentRunner(
        ScriptedLLM(_script(task)[:-1]
                    + ['{"action": {"tool": "think", "args": {"note": "addendum"}}, "thought": "later"}',
                       _script(task)[-1]]),
        builtin_tools(wd_b), os.path.join(wd_b, "journal.jsonl"),
        max_steps=int(task.get("max_steps", 8)), workdir=wd_b,
        run_id="snapshot-drill").run(str(task.get("task_text", "snapshot drill")))
    ev_long, _t = load_trace(os.path.join(wd_b, "journal.jsonl"))

    # torn tail: copy the journal, cut mid-line, recover, travel again
    torn_path = os.path.join(wd, "torn.jsonl")
    raw = open(jp, "rb").read()
    with open(torn_path, "wb") as fh:
        fh.write(raw + b'{"seq": 999, "torn')
    ev_torn, torn_flag = load_trace(torn_path)

    # gapped journal: drop one middle event from a copy of the list
    gapped = [e for e in events if e.seq != max(1, end // 2)]
    empty_err = gap_err = desc_err = beyond_err = ""
    try:
        snapshot_at([], 3)
    except ValueError as e:
        empty_err = str(e)
    try:
        travel(gapped, [len(gapped)])
    except ValueError as e:
        gap_err = str(e)
    try:
        travel(events, [checkpoints[-1], checkpoints[0]])
    except ValueError as e:
        desc_err = str(e)
    try:
        snapshot_at(events, end + 50)
    except ValueError as e:
        beyond_err = str(e)

    tc_at = exp.get("tool_calls_at", {})
    rep_at = exp.get("replies_at", {})
    return [
        Check("run_completes_with_reply",
              result.stop_reason == "reply" and result.reply == exp.get("reply", ""),
              f"{result.stop_reason} {result.reply!r}"),
        Check("final_checkpoint_equals_replay",
              states[-1]["state"] == replay(events)
              and states[-1]["state"]["last_reply"] == exp.get("reply", ""),
              "travel ends exactly where the full fold lands"),
        Check("checkpoint_counters_match",
              all(s["state"]["tool_calls"] == tc_at[str(s["seq"])]
                  and s["state"]["replies"] == rep_at.get(str(s["seq"]),
                                                          s["state"]["replies"])
                  for s in states if str(s["seq"]) in tc_at),
              str([(s["seq"], s["state"]["tool_calls"], s["state"]["replies"])
                   for s in states])),
        Check("prefix_isolation",
              travel(events, checkpoints[:-1]) == travel(ev_long, checkpoints[:-1]),
              "shared prefix folds identically despite later events"),
        Check("torn_tail_isolated",
              torn_flag and [e.seq for e in ev_torn] == [e.seq for e in events]
              and travel(ev_torn, checkpoints) == states,
              "torn trailing line invisible to every checkpoint"),
        Check("travel_deterministic", again == states,
              "two travels, one result"),
        Check("counters_monotone", monotone(states),
              "folded counters never decrease"),
        Check("empty_journal_zero_state",
              snapshot_at([], 0)["state"] == ZERO_STATE
              and empty_err.startswith("checkpoint 3 beyond"),
              "checkpoint 0 is the zero state; beyond is loud"),
        Check("gap_rejected", gap_err.startswith("journal prefix is not dense"),
              gap_err[:60]),
        Check("descending_rejected", desc_err.startswith("checkpoints must be strictly ascending"),
              desc_err[:60]),
        Check("beyond_end_rejected", beyond_err.startswith(f"checkpoint {end + 50} beyond"),
              beyond_err[:60]),
        Check("reopen_stable",
              travel(_reopen(jp), checkpoints) == states
              and not torn and sequence_dense(events),
              "reloaded journal travels identically"),
    ]


def _prompt_drill(task: dict) -> list:
    """Prompt layers: includes in declared order, loud failure contracts.

    Honest contract: include expansion is depth-first and order-preserving
    (verified by marker positions in the real render), diamond includes
    expand once per path, include cycles and self-includes are reported
    with the full path, unknown layers and unresolved variables name
    themselves instead of rendering silent empties, over-deep chains are
    rejected even though they are acyclic, renders are deterministic with
    no leftover directives, and a variable value containing include syntax
    stays literal text — data can never add structure.
    """
    from .prompt import PromptLayers

    exp = _expect(task)
    layers = {str(k): str(v) for k, v in task.get("layers", {}).items()}
    p = PromptLayers(layers)
    out = p.render(str(task.get("entry", "")), dict(task.get("vars", {})))
    markers = [str(m) for m in exp.get("order", [])]
    positions = [out.find(m) for m in markers]
    diamond = p.resolve(str(exp.get("diamond_layer", "")))
    cycle = PromptLayers(dict(exp.get("cycle_layers", {})))
    self_name = str(exp.get("self_layer", ""))
    selfy = PromptLayers({self_name: str(exp.get("self_text", ""))})
    chain = {f"c{i}": f"[[include c{i + 1}]]" for i in range(20)}
    deep = PromptLayers(chain, max_depth=8)
    injection = PromptLayers(
        {str(exp.get("entry_layer", "")): str(exp.get("entry_text", ""))}
    ).render(str(exp.get("entry_layer", "")),
             {"v": str(exp.get("injection_value", ""))})

    def raises_value_error(fn):
        try:
            fn()
            return ""
        except ValueError as e:
            return str(e)

    cycle_err = raises_value_error(lambda: cycle.resolve("a"))
    self_err = raises_value_error(lambda: selfy.resolve(self_name))
    missing_err = raises_value_error(
        lambda: PromptLayers({str(exp.get("missing_include_from", "")):
                              "[[include nope]]"}).resolve(
            str(exp.get("missing_include_from", ""))))
    entry_err = raises_value_error(lambda: p.render("ghost-layer"))
    var_err = raises_value_error(
        lambda: PromptLayers({"x": str(exp.get("missing_var_layer", ""))}
                             ).render("x"))
    deep_err = raises_value_error(lambda: deep.resolve("c0"))
    again = p.render(str(task.get("entry", "")), dict(task.get("vars", {})))
    return [
        Check("layers_render_in_order",
              all(pos >= 0 for pos in positions)
              and all(positions[i] < positions[i + 1]
                      for i in range(len(positions) - 1)),
              str(positions)),
        Check("render_matches_exactly",
              out == exp.get("render", ""),
              repr(out)[:90]),
        Check("nested_include_resolved",
              "[[include" not in out and "{{" not in out,
              "no leftover directives in the final text"),
        Check("diamond_expands_per_path",
              diamond.count(str(exp.get("diamond_marker", ""))) == 2,
              f"marker count={diamond.count(exp.get('diamond_marker', ''))}"),
        Check("cycle_rejected_with_path",
              cycle_err.startswith("include cycle detected: a -> b -> a"),
              cycle_err[:60]),
        Check("self_include_rejected",
              self_err == f"include cycle detected: {self_name} -> {self_name}",
              self_err[:60]),
        Check("missing_include_named",
              missing_err.startswith("unknown layer 'nope'"),
              missing_err[:60]),
        Check("unknown_entry_named",
              entry_err.startswith("unknown layer 'ghost-layer'"),
              entry_err[:60]),
        Check("missing_var_named",
              var_err == "unresolved variables in prompt: missing_var",
              var_err[:60]),
        Check("over_depth_rejected",
              deep_err.startswith("max include depth 8 exceeded"),
              "acyclic 20-layer chain, max_depth 8"),
        Check("render_deterministic", again == out,
              "two renders, byte-identical"),
        Check("substitution_resolves_inside_includes",
              out.count("English") == 1
              and out.count("OpenAgent-X") == 1,
              "vars declared in outer layers resolve inside includes"),
        Check("values_cannot_inject_includes",
              injection == f"value: {exp.get('injection_value', '')}",
              "substituted text is never re-scanned for directives"),
    ]


def _jit_drill(task: dict) -> list:
    """JIT tool disclosure: visibility is policy, and policy is journaled.

    Honest contract: the turn-zero visible set is journaled before any step,
    an undisclosed call is refused with exactly one ``tool_hidden`` event and
    zero side effects (no tool_call, no tool_result, no registry hit), the
    ``tools_expand`` control plane lands as an ordinary journaled call and
    makes its target visible, every visibility change (keyword-driven or
    expansion-driven) is journaled with the full visible set and what was
    added, keyword matching is case-insensitive and deterministic, capped
    rule disclosure truncates in sorted order without hiding the control
    plane, unknown expansion targets and unknown rule tools name themselves,
    and a full re-run in a fresh workspace produces the identical
    (type, payload) event sequence.
    """
    import os
    import tempfile

    from .events import Journal
    from .jit import JITAgentRunner, JITDisclosure, DisclosureRule
    from .llm import ScriptedLLM
    from .tools import ToolError, builtin_tools

    exp = _expect(task)
    rules = [DisclosureRule(tuple(r.get("keywords", ())),
                            tuple(r.get("tools", ())))
             for r in task.get("rules", [])]

    def build(root: str):
        reg = builtin_tools(root)
        disc = JITDisclosure(reg, rules, always=tuple(task.get("always", ("think",))),
                             max_visible=int(task.get("max_visible", 0)))
        runner = JITAgentRunner(ScriptedLLM(task.get("script", [])), reg,
                                os.path.join(root, "journal.jsonl"),
                                disclosure=disc, max_steps=8)
        return disc, runner.run(str(task.get("task", "")))

    tmp1 = tempfile.mkdtemp(prefix="oax-jit-1-")
    disc, res = build(tmp1)
    evs = Journal(os.path.join(tmp1, "journal.jsonl")).events()
    seq = [(e.type, dict(e.payload)) for e in evs]
    discloses = [p for t, p in seq if t == "tool_disclose"]
    hiddens = [p for t, p in seq if t == "tool_hidden"]
    calls = [(p.get("tool"), i) for i, (t, p) in enumerate(seq) if t == "tool_call"]
    results = {p.get("tool"): p for t, p in seq if t == "tool_result"}

    tmp2 = tempfile.mkdtemp(prefix="oax-jit-2-")
    disc2, res2 = build(tmp2)
    evs2 = Journal(os.path.join(tmp2, "journal.jsonl")).events()
    seq2 = [(e.type, dict(e.payload)) for e in evs2]

    # policy-level probes on fresh registries
    probe_reg = builtin_tools(tempfile.mkdtemp(prefix="oax-jit-3-"))
    cap_rule = [DisclosureRule(tuple(exp.get("cap_keywords", ())),
                               tuple(exp.get("cap_tools", ())))]
    probe = JITDisclosure(probe_reg, cap_rule, always=tuple(exp.get("cap_always", ("echo",))),
                          max_visible=int(exp.get("cap_max", 2)))
    cap_added = probe.update(str(exp.get("cap_keywords", [""])[0]))

    case_reg = builtin_tools(tempfile.mkdtemp(prefix="oax-jit-4-"))
    case_disc = JITDisclosure(case_reg, rules)
    case_added = case_disc.update(str(exp.get("case_probe", "")))

    def raises_tool_error(fn):
        try:
            fn()
            return ""
        except ToolError as e:
            return str(e)

    unknown_err = raises_tool_error(
        lambda: JITDisclosure(probe_reg, rules).expand(str(exp.get("unknown_tool", ""))))
    bad_rule = [DisclosureRule(("x",), (str(exp.get("bad_rule_tool", "")),))]

    def raises_value(fn):
        try:
            fn()
            return ""
        except ValueError as e:
            return str(e)

    bad_err = raises_value(lambda: JITDisclosure(probe_reg, bad_rule))
    visible_now = [v["name"] for v in disc.visible_schemas()]

    expand_idx = next((i for name, i in calls
                       if name == str(exp.get("expand_target", ""))), -1)
    calc_calls_before_expand = sum(
        1 for name, i in calls
        if name == str(exp.get("expand_target", "")) and 0 <= expand_idx > i)

    return [
        Check("run_replies_respecting_disclosure",
              res.stop_reason == exp.get("stop_reason")
              and res.steps == int(exp.get("steps", 0))
              and res.reply == exp.get("reply"),
              f"{res.stop_reason} steps={res.steps}"),
        Check("turn_zero_visibility_journaled",
              discloses and discloses[0].get("disclosed") == list(exp.get("first_disclosed", []))
              and discloses[0].get("added") == [],
              str(discloses[0] if discloses else "no tool_disclose")),
        Check("hidden_calls_journaled",
              [p.get("tool") for p in hiddens] == list(exp.get("hidden_tools", []))
              and all(p.get("reason") == "not disclosed" for p in hiddens),
              str([p.get("tool") for p in hiddens])),
        Check("hidden_calls_never_execute",
              calc_calls_before_expand == 0
              and all(name != t for name, _ in calls
                      for t in exp.get("hidden_tools", []) if t != exp.get("expand_target")),
              f"calc before expand: {calc_calls_before_expand}"),
        Check("expand_request_journaled_ok",
              any(name == "tools_expand" for name, _ in calls)
              and results.get("tools_expand", {}).get("ok") is True
              and results["tools_expand"].get("result", {}).get("name")
              == exp.get("expand_target")
              and "schema" in results["tools_expand"].get("result", {}),
              str(results.get("tools_expand", {}).get("result", {}))[:80]),
        Check("expansion_growth_journaled",
              len(discloses) == int(exp.get("disclose_events", 0))
              and discloses[-1].get("added") == [exp.get("expand_target")]
              and discloses[-1].get("disclosed") == list(exp.get("post_expand_disclosed", [])),
              str(discloses[-1] if discloses else "none")),
        Check("calc_executes_after_disclosure",
              sum(1 for name, _ in calls if name == exp.get("expand_target"))
              == int(exp.get("calc_tool_calls", 0))
              and results.get("calc", {}).get("result", {}).get("value")
              == exp.get("calc_value"),
              str(results.get("calc", {}).get("result", {}))[:60]),
        Check("unrevealed_groups_stay_hidden",
              all(t not in {n for p in discloses for n in p.get("disclosed", [])}
                  for t in exp.get("never_visible", [])),
              str(exp.get("never_visible", []))),
        Check("rerun_identical_event_sequence",
              seq == seq2 and res2.stop_reason == res.stop_reason,
              f"{len(seq)} vs {len(seq2)} events"),
        Check("keyword_match_case_insensitive",
              exp.get("expand_target") in case_added,
              str(case_added)),
        Check("cap_truncates_sorted_without_control_loss",
              cap_added == list(exp.get("cap_added", []))
              and all(t not in probe.visible_names()
                      for t in exp.get("cap_absent", []))
              and "tools_expand" in probe.visible_names(),
              f"added={cap_added} visible={probe.visible_names()}"),
        Check("unknown_expand_names_itself",
              unknown_err.startswith(f"unknown tool '{exp.get('unknown_tool', '')}'"),
              unknown_err[:60]),
        Check("rule_with_unknown_tool_rejected",
              str(exp.get("bad_rule_tool", "")) in bad_err,
              bad_err[:60]),
        Check("hidden_tools_absent_from_visibility",
              all(t not in visible_now for t in exp.get("never_visible", []))
              and exp.get("expand_target") in visible_now,
              str(visible_now)),
    ]


def _chaos_drill(task: dict) -> list:
    """Chaos: combined faults injected into ONE run, recovered honestly.

    Honest contract: the deterministic plan is followed exactly (every
    planned LLM outage and tool fault injected, nothing else), RetryLLM
    recovers the model outages while the ledger shows the scars, faulted
    tool calls never reach the real registry (zero side effects: the
    ghost write leaves no file), the faulted results are journaled as
    ordinary ok:false tool_results, the chaos run's event-type stream
    matches a healthy run of the same script, the combined summary is a
    deterministic count map, a full re-run reproduces identical ledgers
    and stream, unplanned tools pass through untouched, and bad plans
    (unknown tool target, sub-1 call numbers) raise naming themselves.
    """
    import os

    from .chain import verify_journal
    from .chaos import ChaosLLM, ChaosTools, chaos_summary
    from .retry import BackoffPolicy, RetryLLM

    wd = _fresh_wd("chaos")
    exp = _expect(task)
    script = _script(task)
    llm_fail_calls = [int(c) for c in exp.get("llm_fail_calls", [])]
    tool_plan = {str(t): int(n)
                 for t, n in dict(exp.get("tool_fail_first", {})).items()}

    def run_chaos(root: str):
        llm = ChaosLLM(ScriptedLLM(list(script)),
                       {c: "planned outage" for c in llm_fail_calls})
        tools = ChaosTools(builtin_tools(root), dict(tool_plan))
        retry = RetryLLM(llm, BackoffPolicy(max_attempts=3, base_delay=0.0))
        jp = os.path.join(root, "journal.jsonl")
        res = AgentRunner(
            retry, tools, jp, max_steps=int(task.get("max_steps", 8)),
            workdir=root, run_id="chaos-drill").run(
                str(task.get("task_text", "chaos drill")))
        events, torn = load_trace(jp)
        return llm, tools, retry, res, events, torn

    llm, tools, retry, res, events, torn = run_chaos(wd)
    types = [e.type for e in events]
    tool_results = [e.payload for e in events if e.type == "tool_result"]
    faulted = [p for p in tool_results if str(p.get("error", "")).startswith("chaos:")]
    calc_results = [p.get("result", {}).get("value")
                    for p in tool_results if p.get("tool") == "calc"]

    healthy_jp = os.path.join(wd, "healthy.jsonl")
    healthy = AgentRunner(ScriptedLLM(list(script)), builtin_tools(wd),
                          healthy_jp, max_steps=int(task.get("max_steps", 8)),
                          workdir=wd, run_id="chaos-healthy").run(
                              str(task.get("task_text", "chaos drill")))
    healthy_types = [e.type for e in load_trace(healthy_jp)[0]]

    wd2 = _fresh_wd("chaos2")
    llm2, tools2, _retry2, res2, events2, _t2 = run_chaos(wd2)

    # side-effect probe: a faulted write must leave NO file behind
    ghost = str(exp.get("ghost_path", "ghost.txt"))
    wd3 = _fresh_wd("chaos3")
    ghost_llm = ChaosLLM(ScriptedLLM([
        '{"action": {"tool": "write_file", "args": {"path": "%s", "text": "x"}}}' % ghost,
        '{"reply": "done"}']), {})
    ghost_tools = ChaosTools(builtin_tools(wd3), {"write_file": 1})
    ghost_res = AgentRunner(ghost_llm, ghost_tools,
                            os.path.join(wd3, "journal.jsonl"),
                            max_steps=4, workdir=wd3,
                            run_id="chaos-ghost").run("ghost probe")
    ghost_results = [e.payload for e in load_trace(
        os.path.join(wd3, "journal.jsonl"))[0] if e.type == "tool_result"]

    # policy probes
    empty = ChaosTools(builtin_tools(_fresh_wd("chaos4")), {})
    echo_out = empty.call("echo", {"text": "hi"})
    unknown_err = ""
    try:
        ChaosTools(builtin_tools(_fresh_wd("chaos5")), {"ghost_tool": 1})
    except ValueError as e:
        unknown_err = str(e)
    one_based_err = ""
    try:
        ChaosLLM(ScriptedLLM([]), {0: "before first call"})
    except ValueError as e:
        one_based_err = str(e)

    combined_ledger = llm.injected + tools.injected
    attempts_ok = [a["ok"] for a in retry.attempts]
    want_ok = [c not in llm_fail_calls
               for c in range(1, llm.calls + 1)]
    return [
        Check("combined_faults_recovered_in_one_run",
              res.stop_reason == "reply" and res.reply == exp.get("reply", ""),
              f"{res.stop_reason} reply={res.reply!r}"),
        Check("llm_outages_exactly_per_plan",
              [e["call"] for e in llm.injected] == llm_fail_calls
              and all(e["kind"] == "llm_outage" for e in llm.injected)
              and llm.calls == len(script) + len(llm_fail_calls),
              f"injected={[e['call'] for e in llm.injected]} "
              f"calls={llm.calls}"),
        Check("tool_faults_exactly_per_plan",
              [e["tool"] for e in tools.injected] == list(tool_plan)
              and all(e["kind"] == "tool_fault" for e in tools.injected),
              str([e["tool"] for e in tools.injected])),
        Check("retry_recovers_with_scars",
              attempts_ok == want_ok
              and sum(1 for a in retry.attempts if not a["ok"])
              == len(llm_fail_calls),
              f"attempts ok={attempts_ok}"),
        Check("faulted_calls_zero_side_effects",
              calc_results == [None, exp.get("calc_value")]
              and tools.passthrough_calls() == len(tool_plan)
              and open(os.path.join(wd, "out.txt"), encoding="utf-8").read()
              == "survived",
              "faulted calc returned no value; the pass-through write landed"),
        Check("ghost_write_never_lands",
              ghost_res.stop_reason == "reply"
              and not os.path.exists(os.path.join(wd3, ghost))
              and all(str(p.get("error", "")).startswith("chaos:")
                      for p in ghost_results if p.get("ok") is False),
              f"ghost exists={os.path.exists(os.path.join(wd3, ghost))}"),
        Check("faulted_results_journaled_honestly",
              len(faulted) == sum(tool_plan.values())
              and all(p.get("ok") is False for p in faulted),
              f"{len(faulted)} faulted tool_results journaled"),
        Check("event_stream_matches_healthy_run",
              types == healthy_types and healthy.stop_reason == "reply",
              f"{len(types)} chaos events vs {len(healthy_types)} healthy"),
        Check("summary_deterministic",
              chaos_summary(combined_ledger)
              == {"llm_outage": len(llm_fail_calls),
                  "tool_fault": sum(tool_plan.values())},
              str(chaos_summary(combined_ledger))),
        Check("rerun_identical_ledgers_and_stream",
              llm2.injected == llm.injected and tools2.injected == tools.injected
              and [e.type for e in events2] == types
              and res2.reply == res.reply,
              "same plan in, same faults out"),
        Check("unplanned_tools_pass_through",
              echo_out == {"ok": True, "result": {"text": "hi"}}
              and empty.injected == [],
              "empty plan never injects"),
        Check("unknown_chaos_target_names_itself",
              "unknown chaos target tool 'ghost_tool'" in unknown_err,
              unknown_err[:60]),
        Check("plan_call_numbers_one_based",
              "1-based" in one_based_err,
              one_based_err[:60]),
        Check("journal_dense_reopen",
              not torn and sequence_dense(events)
              and sequence_dense(_reopen(os.path.join(wd, "journal.jsonl")))
              and verify_journal(os.path.join(wd, "journal.jsonl"))["ok"],
              f"{len(events)} events, dense"),
    ]


def _chain_drill(task: dict) -> list:
    """Hash-chained traces: every line committed, every edit localized.

    Honest contract: a runner-written ChainedJournal verifies with stored
    digests equal to an independent recomputation, the seal equals the head
    and re-verification is stable, editing any stored byte of line *k*
    breaks the chain at *k* (payload or ts), deletion and reorder break at
    the first mislinked line, the head changes under tampering, a torn
    tail isolates with an intact but unsealable prefix, plain journals
    verify honestly as chained:false and refuse to seal, an empty journal
    reports the zero state honestly, and appending to a chained journal
    continues the chain.
    """
    import json as _json

    from .chain import (ChainError, ChainedJournal, compute_chain, head_of,
                        seal, verify_journal)
    from .events import Journal, read_events

    wd = _fresh_wd("chain")
    exp = _expect(task)
    jp = os.path.join(wd, "journal.jsonl")
    res = AgentRunner(ScriptedLLM(_script(task)), builtin_tools(wd), jp,
                      max_steps=int(task.get("max_steps", 8)), workdir=wd,
                      run_id="chain-drill",
                      journal_cls=ChainedJournal).run(
                          str(task.get("task_text", "chain drill")))
    r1 = verify_journal(jp)
    events = read_events(jp)
    lines = open(jp, encoding="utf-8").read().splitlines()

    def rewrite(name: str, mutate) -> dict:
        """Copy the journal, apply mutate(lines), verify the copy."""
        copy = list(lines)
        mutate(copy)
        path = os.path.join(wd, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(copy) + "\n")
        return verify_journal(path)

    def edit_payload(copy):
        obj = _json.loads(copy[exp.get("edit_index", 2)])
        obj["payload"]["drill_note"] = "EVIL"
        copy[exp.get("edit_index", 2)] = _json.dumps(obj, sort_keys=True,
                                                     ensure_ascii=False)

    def edit_ts(copy):
        obj = _json.loads(copy[1])
        obj["ts"] = obj["ts"] + 0.5
        copy[1] = _json.dumps(obj, sort_keys=True, ensure_ascii=False)

    def delete_line(copy):
        del copy[1]

    def reorder(copy):
        copy[0], copy[1] = copy[1], copy[0]

    r_edit = rewrite("edited.jsonl", edit_payload)
    r_ts = rewrite("ts.jsonl", edit_ts)
    r_del = rewrite("deleted.jsonl", delete_line)
    r_reo = rewrite("reordered.jsonl", reorder)

    def seal_error(path) -> str:
        try:
            seal(path)
            return ""
        except ChainError as e:
            return str(e)

    edit_idx = int(exp.get("edit_index", 2))
    torn_path = os.path.join(wd, "torn.jsonl")
    with open(torn_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n" + '{"seq": 99, "tu')
    r_torn = verify_journal(torn_path)

    plain = os.path.join(wd, "plain.jsonl")
    j = Journal(plain)
    j.start_run("chain-plain")
    j.append("run_start", {"task": "legacy"})
    j.append("reply", {"text": "hi"})
    r_plain = verify_journal(plain)

    empty = verify_journal(os.path.join(wd, "empty.jsonl"))

    # capture the pristine seal + re-read stability BEFORE the resume append
    sealed_head = seal(jp)
    r_stable = verify_journal(jp)

    resume = ChainedJournal(jp)
    resume.start_run(res.run_id)
    resume.append("note", {"text": "appended later"})
    r_resume = verify_journal(jp)

    seal_msg = seal_error(os.path.join(wd, "edited.jsonl"))
    return [
        Check("runner_chained_journal_verifies",
              res.stop_reason == "reply" and res.reply == exp.get("reply", "")
              and r1["ok"] and r1["chained"] and r1["n"] == res.events
              and r1["broken_at"] == -1 and not r1["torn_tail"],
              f"{r1['n']} events head={r1['head'][:12]}"),
        Check("stored_digests_match_independent_chain",
              compute_chain(events)[-1] == r1["head"] == head_of(events),
              "stored chain equals a from-scratch recomputation"),
        Check("seal_matches_head_and_is_stable",
              sealed_head == r1["head"] and r_stable == r1,
              "seal is exactly the verified head"),
        Check("payload_edit_localized",
              not r_edit["ok"] and r_edit["broken_at"] == edit_idx,
              f"edit at {edit_idx} -> broken_at={r_edit['broken_at']}"),
        Check("ts_tamper_detected",
              not r_ts["ok"] and r_ts["broken_at"] == 1,
              "every stored byte is covered, including ts"),
        Check("deletion_breaks_chain",
              not r_del["ok"] and r_del["broken_at"] == 1,
              f"delete -> broken_at={r_del['broken_at']}"),
        Check("reorder_breaks_chain",
              not r_reo["ok"] and r_reo["broken_at"] == 0,
              f"reorder -> broken_at={r_reo['broken_at']}"),
        Check("head_changes_under_tampering",
              r_edit["head"] != r1["head"] and r_del["head"] != r1["head"],
              "a previously recorded seal no longer matches"),
        Check("seal_refuses_broken",
              f"broken at index {edit_idx}" in seal_msg,
              seal_msg[:60]),
        Check("torn_tail_prefix_ok_unsealable",
              r_torn["torn_tail"] and r_torn["ok"]
              and r_torn["n"] == r1["n"]
              and "torn tail" in seal_error(torn_path),
              "prefix intact, file incomplete, seal refuses"),
        Check("plain_journal_verifies_unchained",
              r_plain["ok"] and not r_plain["chained"]
              and r_plain["n"] == 2 and r_plain["head"]
              and "not chain-written" in seal_error(plain),
              "legacy journals verify honestly and refuse to seal"),
        Check("empty_journal_honest",
              empty["ok"] and empty["n"] == 0 and empty["head"] == ""
              and "nothing to seal" in seal_error(os.path.join(wd, "empty.jsonl")),
              "the zero state is reported, not faked"),
        Check("chained_resume_continues",
              r_resume["ok"] and r_resume["chained"]
              and r_resume["n"] == r1["n"] + 1,
              f"resumed chain: {r_resume['n']} events"),
        Check("journal_dense_reopen",
              sequence_dense(events)
              and sequence_dense(_reopen(jp)),
              f"{len(events)} events, dense across reopens"),
    ]


def _diff_drill(task: dict) -> list:
    """Journal diff: the same script twice is semantically SAME, every
    mutation localizes.

    Honest contract: two independent runs of one script differ only in
    wall-clock ts (semantic diff says SAME, strict mode says DIFFERENT at
    seq 0), a self-diff is the zero diff, an edited reply localizes at the
    reply's seq with both tails carried verbatim, deletion and addition are
    reported on the right side, torn tails isolate per side, type counts
    match the raw stream, renders are byte-deterministic, and the CLI exit
    contract (0 = same, 1 = different) holds.
    """
    from .cli import main as cli_main
    from .jdiff import diff_journals, render_diff

    wd = _fresh_wd("diff")
    events, result = _run_offline(task, wd, "a.jsonl")
    wd2 = _fresh_wd("diff")
    _run_offline(task, wd2, "b.jsonl")
    jp_a = os.path.join(wd, "a.jsonl")
    jp_b = os.path.join(wd2, "b.jsonl")
    exp = _expect(task)

    def copy_with(name, mutate):
        dst = os.path.join(wd, name)
        lines = open(jp_a, encoding="utf-8").read().splitlines()
        mutate(lines)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return dst

    def edit_reply(lines):
        for i, ln in enumerate(lines):
            obj = json.loads(ln)
            if obj.get("type") == "reply":
                obj["payload"]["text"] = "TAMPERED"
                lines[i] = json.dumps(obj, sort_keys=True, ensure_ascii=False)
                return

    def drop_last(lines):
        del lines[-1]

    def append_note(lines):
        obj = json.loads(lines[-1])
        obj["seq"] = len(lines)
        obj["type"] = "note"
        obj["payload"] = {"text": "extra"}
        obj["ts"] = obj["ts"] + 1.0
        lines.append(json.dumps(obj, sort_keys=True, ensure_ascii=False))

    jp_edit = copy_with("edited.jsonl", edit_reply)
    jp_drop = copy_with("dropped.jsonl", drop_last)
    jp_plus = copy_with("plus.jsonl", append_note)
    jp_torn_b = os.path.join(wd2, "torn-b.jsonl")
    with open(jp_torn_b, "wb") as fh:
        fh.write(open(jp_b, "rb").read() + b'{"seq": 99, "tu')

    r_same = diff_journals(jp_a, jp_b)
    r_self = diff_journals(jp_a, jp_a)
    r_edit = diff_journals(jp_a, jp_edit)
    r_drop = diff_journals(jp_a, jp_drop)
    r_plus = diff_journals(jp_a, jp_plus)
    r_strict = diff_journals(jp_a, jp_b, strict=True)
    r_torn = diff_journals(jp_a, jp_torn_b)
    rendered = render_diff(r_edit)
    render_twice = render_diff(diff_journals(jp_a, jp_edit))

    reply_seq = next(e.seq for e in events if e.type == "reply")
    counts: dict = {}
    for e in events:
        counts[e.type] = counts.get(e.type, 0) + 1
    reply_text = str(exp.get("reply", ""))

    return [
        Check("both_runs_stop_reply",
              result.stop_reason == "reply" and result.reply == reply_text,
              f"stop={result.stop_reason}"),
        Check("same_script_is_semantically_same",
              r_same["same"] and r_same["diverged_at"] == -1
              and r_same["removed_count"] == 0 and r_same["added_count"] == 0,
              f"common={r_same['common']}/{r_same['events_a']}"),
        Check("self_diff_is_zero",
              r_self["same"] and r_self["diverged_at"] == -1,
              "a journal against itself is the zero diff"),
        Check("edited_reply_localizes",
              not r_edit["same"] and r_edit["diverged_at"] == reply_seq
              and r_edit["removed"][0]["payload"]["text"] == reply_text
              and r_edit["added"][0]["payload"]["text"] == "TAMPERED",
              f"diverged_at={r_edit['diverged_at']} (reply seq {reply_seq})"),
        Check("deletion_reported_as_removed",
              not r_drop["same"] and r_drop["removed_count"] == 1
              and r_drop["added_count"] == 0,
              "missing run_end lands on the removed side"),
        Check("addition_reported_as_added",
              not r_plus["same"] and r_plus["added_count"] == 1
              and r_plus["removed_count"] == 0
              and r_plus["added"][0]["type"] == "note",
              "the extra event lands on the added side"),
        Check("strict_mode_sees_ts_noise",
              not r_strict["same"] and r_strict["diverged_at"] == 0,
              "wall-clock is data under --strict"),
        Check("torn_tail_isolated_per_side",
              r_torn["same"] and r_torn["torn_b"] and not r_torn["torn_a"],
              "garbage tail never corrupts the comparison"),
        Check("type_counts_match_stream",
              r_same["type_counts_a"] == counts
              and sum(counts.values()) == len(events),
              str(counts)[:70]),
        Check("render_deterministic_and_informative",
              rendered == render_twice and "DIFFERENT" in rendered
              and "- seq=" in rendered and "+ seq=" in rendered,
              "byte-identical renders with +/- lines"),
        Check("cli_exit_contract",
              cli_main(["diff", jp_a, jp_b]) == 0
              and cli_main(["diff", jp_a, jp_edit]) == 1,
              "0 = same, 1 = different"),
        Check("journals_dense_reopen",
              sequence_dense(events) and sequence_dense(_reopen(jp_a)),
              f"{len(events)} events, dense"),
    ]


def _stats_drill(task: dict) -> list:
    """Run analytics: the numeric fingerprint agrees with every other view.

    Honest contract: counters are taken from replay() itself so stats and
    replay can never disagree, type counts match the raw stream, per-tool
    pairing sums to the call count with the planned failure visible, think
    is graded as the tool it is, the empty journal reports the zero state,
    a torn tail is reported honestly with the prefix counted, renders are
    byte-deterministic, and the CLI contract holds.
    """
    from .cli import main as cli_main
    from .stats import render_stats, run_stats
    from .trace import replay

    wd = _fresh_wd("stats")
    events, result = _run_offline(task, wd)
    jp = os.path.join(wd, "journal.jsonl")
    exp = _expect(task)
    s = run_stats(jp)
    st = replay(events)
    counts: dict = {}
    for e in events:
        counts[e.type] = counts.get(e.type, 0) + 1

    empty_path = os.path.join(wd, "empty.jsonl")
    open(empty_path, "w", encoding="utf-8").close()
    s_empty = run_stats(empty_path)

    torn_path = os.path.join(wd, "torn.jsonl")
    with open(torn_path, "wb") as fh:
        fh.write(open(jp, "rb").read() + b'{"seq": 99, "tu')
    s_torn = run_stats(torn_path)

    exp_calls = int(exp.get("tool_calls", s["tool_calls"]))
    exp_fails = int(exp.get("tool_fails", s["tool_fails"]))
    return [
        Check("run_stops_as_planned",
              result.stop_reason == exp.get("stop_reason", "reply")
              and result.reply == str(exp.get("reply", "")),
              f"stop={result.stop_reason}"),
        Check("event_count_honest",
              s["events"] == len(events) and s["dense"] and not s["torn_tail"],
              f"{s['events']} events, dense={s['dense']}"),
        Check("replay_agreement",
              s["thoughts"] == st["thoughts"] and s["steps"] == st["steps"]
              and s["tool_calls"] == st["tool_calls"]
              and s["tool_results"] == st["tool_results"]
              and s["replies"] == st["replies"] and s["errors"] == st["errors"]
              and s["redactions"] == st["redactions"]
              and s["runs_opened"] == st["runs_opened"]
              and s["runs_closed"] == st["runs_closed"],
              "stats are replay's numbers — one source of truth"),
        Check("type_counts_match_stream",
              s["type_counts"] == counts and sum(counts.values()) == s["events"],
              str(counts)[:70]),
        Check("tool_profile_as_planned",
              s["tool_calls"] == exp_calls and s["tool_fails"] == exp_fails,
              f"calls={s['tool_calls']} fails={s['tool_fails']}"),
        Check("per_tool_pairing_sums",
              all(t["calls"] == t["ok"] + t["failed"]
                  for t in s["tools"].values())
              and any(t["failed"] for t in s["tools"].values()),
              str(s["tools"])[:70]),
        Check("think_is_a_tool", "think" in s["tools"],
              "the think turn is counted where it belongs"),
        Check("duration_reported_not_graded",
              isinstance(s["duration"], float) and s["duration"] >= 0.0,
              f"{s['duration']}s"),
        Check("render_deterministic_and_labeled",
              render_stats(run_stats(jp)) == render_stats(s)
              and "wall-clock" in render_stats(s),
              "byte-identical re-render"),
        Check("empty_journal_zero_state",
              s_empty["events"] == 0 and s_empty["dense"] and not s_empty["torn_tail"]
              and s_empty["type_counts"] == {} and s_empty["tools"] == {}
              and s_empty["duration"] == 0.0,
              "the zero state is reported, not faked"),
        Check("torn_tail_reported_with_prefix",
              s_torn["torn_tail"] and s_torn["events"] == s["events"],
              "garbage tail isolated, prefix counted"),
        Check("cli_contract",
              cli_main(["stats", jp]) == 0
              and cli_main(["stats", os.path.join(wd, "gone.jsonl")]) == 1,
              "0 = report, 1 = missing file"),
    ]


def _bench_drill(task: dict) -> list:
    """Journal microbench: structure is graded, wall-clock never is.

    Honest contract: every planned event lands dense with rates reported,
    bytes are re-statted from disk, the read-back returns exactly the
    planned count, doubling the workload doubles the journal, the
    zero-event bench exposes the empty journal with 0.0 rates instead of
    dividing by zero, the render labels timings as never-graded, and the
    CLI contract holds. No check ever asserts a timing value.
    """
    from .bench import render_bench, run_bench
    from .cli import main as cli_main

    wd = _fresh_wd("bench")
    exp = _expect(task)
    n = int(exp.get("events", 300))
    b1 = run_bench(events=n, workdir=os.path.join(wd, "b1"))
    b2 = run_bench(events=n, workdir=os.path.join(wd, "b2"))
    b0 = run_bench(events=0, workdir=os.path.join(wd, "b0"))
    b2x = run_bench(events=2 * n, workdir=os.path.join(wd, "b2x"))
    back, torn = read_events_safe(b1["journal"])
    rendered = render_bench(b1)

    timing_keys = ("append_s", "read_s", "replay_s")
    return [
        Check("bench_lands_all_events",
              b1["events"] == n == b1["planned_events"] and b1["dense"]
              and not b1["torn_tail"],
              f"{b1['events']}/{n} dense={b1['dense']}"),
        Check("rates_reported_positive",
              b1["append_eps"] > 0 and b1["read_eps"] > 0
              and b1["replay_eps"] > 0,
              f"append={b1['append_eps']} read={b1['read_eps']} "
              f"replay={b1['replay_eps']} ev/s"),
        Check("timings_are_floats_never_asserted",
              all(isinstance(b1[k], float) and b1[k] >= 0 for k in timing_keys),
              "structure only — the clock is nobody's grade"),
        Check("bytes_re_statted_from_disk",
              b1["journal_bytes"] == os.path.getsize(b1["journal"]) > 0,
              f"{b1['journal_bytes']} bytes"),
        Check("readback_equals_planned",
              len(back) == n and not torn,
              f"read back {len(back)}"),
        Check("render_labeled_and_sectioned",
              all(w in rendered for w in
                  ("append", "read", "replay", "events/sec", "never graded")),
              "the honesty label is part of the report"),
        Check("structure_stable_across_runs",
              sorted(b1.keys()) == sorted(b2.keys()),
              f"{len(b1.keys())} report keys"),
        Check("scale_doubles_the_journal",
              b2x["events"] == 2 * n and b2x["journal_bytes"] > b1["journal_bytes"],
              f"{n}->{2 * n} events, bytes {b1['journal_bytes']}->"
              f"{b2x['journal_bytes']}"),
        Check("zero_events_honest",
              b0["events"] == 0 and b0["dense"] and b0["append_eps"] == 0.0
              and b0["read_eps"] == 0.0 and b0["journal_bytes"] == 0,
              "0.0 rates instead of a division by zero"),
        Check("report_names_its_journal",
              b1["journal"].endswith(".jsonl") and os.path.exists(b1["journal"]),
              str(b1["journal"])[:60]),
        Check("cli_contract", cli_main(["bench", "--events", "60"]) == 0,
              "exit 0 = planned events landed dense"),
        Check("workload_is_deterministic",
              b1["journal_bytes"] > 0 and b2["journal_bytes"] > 0
              and abs(b1["journal_bytes"] - b2["journal_bytes"])
              <= max(64, b1["journal_bytes"] // 100),
              "same workload, near-identical bytes (ts digits drift only)"),
    ]


def _fuzz_drill(task: dict) -> list:
    """Seeded fuzz: the journal contract holds under randomized attack.

    Honest contract: the fixed schedule (torn tail every 7th op, middle
    tear every 11th op) fires exactly as computed, torn tails isolate and
    truncate cleanly, middle tears raise and restore byte-identically,
    every payload round-trips including unicode, two reads fold to the
    same replay state, reports carry no timings so the same seed always
    yields the same verdict, and the CLI contract holds.
    """
    from .cli import main as cli_main
    from .fuzz import render_fuzz, run_fuzz, run_fuzz_suite

    wd = _fresh_wd("fuzz")
    exp = _expect(task)
    ops = int(exp.get("ops", 90))
    seeds = [int(s) for s in exp.get("seeds", [0, 1, 2])]
    suite = run_fuzz_suite(seeds=seeds, n_ops=ops, workdir=wd)
    exp_torn = len([i for i in range(ops) if i % 7 == 3])
    exp_mid = len([i for i in range(ops) if i % 11 == 5])

    r_a = run_fuzz(seed=11, n_ops=45, workdir=wd)
    r_b = run_fuzz(seed=11, n_ops=45, workdir=wd)
    r_c = run_fuzz(seed=12, n_ops=45, workdir=os.path.join(wd, "twelve"))
    r0 = run_fuzz(seed=13, n_ops=0, workdir=os.path.join(wd, "zero"))
    a_ev = _reopen(r_a["journal"])
    c_ev = _reopen(r_c["journal"])
    rendered = render_fuzz(suite[0])

    return [
        Check("suite_clean_on_all_seeds",
              len(suite) == len(seeds) and all(r["ok"] and not r["violations"]
                                               for r in suite),
              f"{len(suite)} seeds x {ops} ops, 0 violations"),
        Check("torn_schedule_fired_exactly",
              all(r["torn_injected"] == exp_torn for r in suite),
              f"{exp_torn} torn-tail injections per seed"),
        Check("middle_tears_raised_and_restored",
              all(r["middle_tears"] == exp_mid for r in suite),
              f"{exp_mid} splices per seed, each must raise then restore"),
        Check("roundtrip_including_unicode",
              all(r["roundtrip"] for r in suite),
              "every (seq,type,payload) came back equal from disk"),
        Check("checks_exceed_ops",
              all(r["checks_run"] >= r["n_ops"] for r in suite),
              f"min checks {min(r['checks_run'] for r in suite)}"),
        Check("report_is_fully_deterministic",
              r_a == r_b,
              "no timings: same seed -> identical report dict"),
        Check("seed_changes_the_trace",
              [(e.type, json.dumps(e.payload, sort_keys=True)) for e in a_ev[:8]]
              != [(e.type, json.dumps(e.payload, sort_keys=True)) for e in c_ev[:8]]
              and r_a["ok"] and r_c["ok"],
              "different seeds drive different random payloads"),
        Check("dense_final_journals",
              all(r["dense"] for r in suite) and r_a["dense"] and r_c["dense"],
              "dense sequences survive the whole attack schedule"),
        Check("ok_flag_matches_violations",
              all(r["ok"] == (not r["violations"]) for r in suite),
              "the verdict flag is never independent of the evidence"),
        Check("zero_ops_honest",
              r0["events_written"] == 0 and r0["ok"] and r0["dense"]
              and r0["torn_injected"] == 0 and r0["checks_run"] >= 3,
              "the zero state still verifies and reports"),
        Check("render_deterministic_one_line",
              rendered == render_fuzz(run_fuzz(seed=suite[0]["seed"],
                                               n_ops=ops,
                                               workdir=wd))
              and " OK" in rendered,
              "same seed -> byte-identical verdict line"),
        Check("cli_contract",
              cli_main(["fuzz", "--seeds", "21,22", "--ops", "35"]) == 0,
              "exit 0 = zero violations across seeds"),
    ]


def _property_drill(task: dict) -> list:
    """Property suite: invariants re-demanded after every step of a trace.

    Honest contract: every seed's random trace ends clean with the torn
    tails isolated, the strict reader having refused every one of them,
    truncation having restored the exact pre-tear bytes, density
    re-checked after every single op, the round-trip matching the written
    plan, replay proven ts-independent, reports deterministic (no
    timings), different seeds driving different traces, the zero-op run
    still verifying, and the CLI contract holding.
    """
    from .cli import main as cli_main
    from .property import (render_property, run_property_suite,
                           run_property_trace)

    wd = _fresh_wd("property")
    exp = _expect(task)
    ops = int(exp.get("ops", 60))
    seeds = [int(s) for s in exp.get("seeds", [0, 1, 2])]
    suite = run_property_suite(seeds=seeds, n_ops=ops, workdir=wd)

    r_a = run_property_trace(seed=11, n_ops=45, workdir=wd)
    r_b = run_property_trace(seed=11, n_ops=45, workdir=wd)
    r_c = run_property_trace(seed=12, n_ops=45, workdir=os.path.join(wd, "twelve"))
    r0 = run_property_trace(seed=13, n_ops=0, workdir=os.path.join(wd, "zero"))
    a_ev = _reopen(r_a["journal"])
    c_ev = _reopen(r_c["journal"])
    rendered = render_property(suite[0])

    return [
        Check("suite_clean_on_all_seeds",
              len(suite) == len(seeds) and all(r["ok"] and not r["violations"]
                                               for r in suite),
              f"{len(suite)} seeds x {ops} steps, 0 violations"),
        Check("torn_tails_always_isolated",
              all(r["torn_injected"] > 0
                  and r["torn_isolated"] == r["torn_injected"]
                  and r["strict_refusals"] == r["torn_injected"]
                  for r in suite),
              f"min {min(r['torn_injected'] for r in suite)} tears/seed, "
              f"every one isolated and strictly refused"),
        Check("truncation_restores_exact_bytes",
              all(r["byte_exact_resumes"] == r["torn_injected"]
                  for r in suite),
              "every tear ended byte-identical to the pre-tear file"),
        Check("density_rechecked_after_every_step",
              all(r["reads_checked"] == r["n_ops"] and r["dense"]
                  for r in suite),
              f"{ops} full read-backs per seed, all dense"),
        Check("roundtrip_matches_written_plan",
              all(r["events_written"] == r["appends"] and r["appends"] > 0
                  for r in suite),
              f"min {min(r['appends'] for r in suite)} appends/seed, "
              f"nothing lost or invented"),
        Check("replay_is_ts_independent",
              all(r["ts_invariant"] for r in suite),
              "a different wall-clock folds to the identical state"),
        Check("report_fully_deterministic",
              r_a == r_b,
              "no timings: same seed -> identical report dict"),
        Check("seed_changes_the_trace",
              [(e.type, json.dumps(e.payload, sort_keys=True)) for e in a_ev[:8]]
              != [(e.type, json.dumps(e.payload, sort_keys=True)) for e in c_ev[:8]]
              and r_a["ok"] and r_c["ok"],
              "different seeds drive different random traces"),
        Check("writer_restarts_resume_dense",
              all(r["resumes"] > 0 for r in suite)
              and all(len(_reopen(r["journal"])) == r["events_written"]
                      for r in suite),
              f"min {min(r['resumes'] for r in suite)} restarts/seed, "
              f"all resumed dense"),
        Check("zero_ops_honest",
              r0["events_written"] == 0 and r0["ok"] and r0["dense"]
              and r0["torn_injected"] == 0 and r0["checks_run"] >= 3,
              "the zero state still verifies and reports"),
        Check("render_deterministic_one_line",
              rendered == render_property(run_property_trace(
                  seed=suite[0]["seed"], n_ops=ops, workdir=wd))
              and " OK" in rendered,
              "same seed -> byte-identical verdict line"),
        Check("cli_contract",
              cli_main(["property", "--seeds", "31,32", "--ops", "35"]) == 0,
              "exit 0 = zero violations across seeds"),
    ]


def _pack2_drill(task: dict) -> list:
    """Signed manifests v2: authenticity (HMAC) on top of integrity (v1).

    Honest contract: the signature covers the canonical sig-stripped
    bytes, signings are deterministic, key_id names without revealing,
    wrong keys and edited entries fail the signature while tampered
    files fail the content layer (both layers always reported), the
    unsigned form is refused, v1 still accepts the core, and the CLI
    contract holds in both directions.
    """
    from .cli import main as cli_main
    from .pack import verify_manifest
    from .pack2 import (derive_key_id, sign_manifest, signed_json,
                        verify_signature, verify_signed, write_signed)

    wd = _fresh_wd("pack2")
    with open(os.path.join(wd, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("alpha payload\n")
    os.makedirs(os.path.join(wd, "sub"))
    with open(os.path.join(wd, "sub", "b.json"), "w", encoding="utf-8") as fh:
        fh.write('{"n": 1}\n')
    with open(os.path.join(wd, "notes.md"), "w", encoding="utf-8") as fh:
        fh.write("# notes\n")
    exp = _expect(task)
    want_files = int(exp.get("files", 3))
    key = "oax-" + "sign" + "-key-v2"  # runtime concatenation, never a literal

    m1 = sign_manifest(wd, key)
    m2 = sign_manifest(wd, key)
    signed_path = os.path.join(wd, "pack.signed.json")
    write_signed(wd, key, signed_path)
    with open(signed_path, encoding="utf-8") as fh:
        loaded = json.load(fh)
    ok, probs = verify_signed(wd, loaded, key)

    bad_entry = json.loads(json.dumps(loaded))
    bad_entry["files"][0]["sha256"] = "0" * 64
    edit_ok, edit_probs = verify_signed(wd, bad_entry, key)

    with open(os.path.join(wd, "a.txt"), "a", encoding="utf-8") as fh:
        fh.write("tampered\n")
    tamper_ok, tamper_probs = verify_signed(wd, loaded, key)
    with open(os.path.join(wd, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("alpha payload\n")
    restore_ok, restore_probs = verify_signed(wd, loaded, key)

    wrong_ok, wrong_probs = verify_signed(wd, loaded, "another-key-entirely")
    unsigned = {k: v for k, v in loaded.items() if k != "sig"}
    unsigned_ok, unsigned_probs = verify_signed(wd, unsigned, key)
    other = sign_manifest(wd, "key-" + "number-two")

    cli_out = os.path.join(wd, "pack.signed.json")  # the flavor the hasher skips
    cli_sign = cli_main(["pack2", wd, "--key", key, "--out", cli_out]) == 0
    cli_check = cli_main(["pack2", wd, "--key", key, "--check", cli_out]) == 0
    cli_bad = cli_main(["pack2", wd, "--key", key + "x", "--check", cli_out])

    return [
        Check("manifest_shape_and_files",
              m1["file_count"] == want_files and m1.get("v") == 2
              and [e["path"] for e in m1["files"]]
              == ["a.txt", "notes.md", "sub/b.json"],
              f"{m1['file_count']} files hashed, v2 envelope"),
        Check("signature_roundtrip",
              ok and not probs and m1["sig"]["algo"] == "hmac-sha256",
              "sign -> write -> load -> verify green"),
        Check("deterministic_signed_bytes",
              signed_json(m1) == signed_json(m2),
              "same tree + key -> byte-identical signed manifest"),
        Check("key_id_names_never_reveals",
              m1["sig"]["key_id"] == derive_key_id(key)
              and len(m1["sig"]["key_id"]) == 12
              and key not in signed_json(m1),
              f"key_id={m1['sig']['key_id']}, key absent from bytes"),
        Check("wrong_key_fails",
              not wrong_ok and any("bad signature" in p for p in wrong_probs),
              "a different key never opens the manifest"),
        Check("edited_entry_fails_signature",
              not edit_ok and any("bad signature" in p for p in edit_probs),
              "flipping one hash byte breaks the HMAC"),
        Check("tampered_file_detected_on_content_layer",
              not tamper_ok and any("modified: a.txt" in p for p in tamper_probs)
              and verify_signature(loaded, key),
              "signature green, content red — both layers reported"),
        Check("unsigned_form_refused",
              not unsigned_ok
              and any("unsigned" in p for p in unsigned_probs),
              "the sig-stripped manifest is not a v2 manifest"),
        Check("v1_verifier_accepts_the_core",
              verify_manifest(wd, unsigned)[0],
              "the v1 integrity layer reads the core unchanged"),
        Check("different_key_different_signature",
              other["sig"]["digest"] != m1["sig"]["digest"]
              and other["sig"]["key_id"] != m1["sig"]["key_id"],
              "keys never collide on id or digest"),
        Check("restore_goes_green",
              restore_ok and not restore_probs,
              "restoring the tree verifies again"),
        Check("cli_contract",
              cli_sign and cli_check and cli_bad == 1,
              "sign 0 / check 0 / wrong-key check 1"),
    ]


def _graph_drill(task: dict) -> list:
    """Dependency graph: structure derived from source, cycles are data.

    Honest contract: the eager graph is acyclic with nothing unresolved,
    edges resolve to real modules (sorted, deduplicated), fan sums equal
    the eager edge count, the base layer and CLI surface are real,
    lazy imports are recorded as lazy edges and the package's real
    deferred-import cycle is reported as data without contaminating the
    eager layers, synthetic eager cycles kill the layering while
    lazy-only cycles keep it, rebuilds are byte-identical, and the CLI
    contract holds (0 acyclic / 1 cyclic).
    """
    from .cli import main as cli_main
    from .depgraph import build_depgraph, depgraph_json

    exp = _expect(task)
    min_edges = int(exp.get("min_eager_edges", 30))
    min_depth = int(exp.get("min_depth", 4))
    g = build_depgraph(".")
    g2 = build_depgraph(".")
    eager = [e for e in g["edges"] if e["kind"] == "eager"]

    # synthetic packages: an eager two-module cycle vs a lazy-only cycle
    wd = _fresh_wd("graph")
    cyc = os.path.join(wd, "cycpkg")
    os.makedirs(cyc)
    with open(os.path.join(cyc, "__init__.py"), "w", encoding="utf-8") as fh:
        fh.write("")
    with open(os.path.join(cyc, "a.py"), "w", encoding="utf-8") as fh:
        fh.write("from .b import x\n")
    with open(os.path.join(cyc, "b.py"), "w", encoding="utf-8") as fh:
        fh.write("from .a import x\n")
    gc = build_depgraph(wd, cyc)

    laz = os.path.join(wd, "lazy")
    os.makedirs(laz)
    with open(os.path.join(laz, "__init__.py"), "w", encoding="utf-8") as fh:
        fh.write("")
    with open(os.path.join(laz, "m.py"), "w", encoding="utf-8") as fh:
        fh.write("def f():\n    from .n import g\n    return g\n")
    with open(os.path.join(laz, "n.py"), "w", encoding="utf-8") as fh:
        fh.write("def g():\n    from .m import f\n    return f\n")
    gl = build_depgraph(laz, laz)

    cli_out = os.path.join(wd, "graph.json")
    cli_ok = cli_main(["graph", "--out", cli_out]) == 0
    with open(cli_out, encoding="utf-8") as fh:
        cli_loaded = json.load(fh)
    cli_cyclic = cli_main(["graph", "--pkg-dir", cyc])

    return [
        Check("eager_graph_acyclic",
              g["acyclic"] and not g["cycles"] and not g["unresolved"],
              f"{g['eager_count']} eager edges, 0 cycles, 0 unresolved"),
        Check("edges_resolved_sorted_deduped",
              eager == sorted(eager, key=lambda e: (e["from"], e["to"]))
              and len({(e["from"], e["to"]) for e in eager}) == len(eager)
              and all(e["from"].startswith("openagentx.")
                      and e["to"].startswith("openagentx.") for e in eager),
              "every edge is a real package-qualified pair"),
        Check("fan_sums_match_edges",
              sum(g["fan_in"].values()) == sum(g["fan_out"].values())
              == len(eager) == g["eager_count"] >= min_edges,
              f"{g['eager_count']} eager edges, sums agree"),
        Check("base_layer_is_real",
              g["layers"]["openagentx.events"] == 0
              and g["layers"]["openagentx.redact"] == 0
              and "openagentx.events" in g["leaves"],
              "stdlib-only modules sit at layer 0 as leaves"),
        Check("cli_surface_reached",
              "openagentx.__main__" in g["entries"] and g["depth"] >= min_depth,
              f"depth {g['depth']}, __main__ imports nothing"),
        Check("lazy_edges_recorded",
              g["lazy_count"] > 0
              and any(e["kind"] == "lazy" for e in g["edges"]),
              f"{g['lazy_count']} deferred imports as data"),
        Check("real_lazy_cycle_reported",
              any("openagentx.cli" in c for c in g["lazy_cycles"])
              and not any("openagentx.cli" in c for c in g["cycles"]),
              "the cli/doctor/evaluation/sbom deferral ring, out loud"),
        Check("deterministic_graph",
              depgraph_json(g) == depgraph_json(g2)
              and g["graph_sha256"] == g2["graph_sha256"],
              "same package -> byte-identical graph"),
        Check("sbom_agreement",
              g["module_count"] == g["node_count"] >= 30
              and g["stdlib_only"] is True and not g["network_modules"],
              "one package, one module count, computed purity"),
        Check("eager_cycle_kills_layers",
              gc["cycles"] and gc["layers"] is None and gc["depth"] is None
              and not gc["acyclic"],
              "a real cycle is reported, never papered over"),
        Check("lazy_only_cycle_keeps_layers",
              not gl["cycles"] and gl["lazy_cycles"]
              and gl["layers"] is not None,
              "deferred imports do not taint the eager layering"),
        Check("cli_contract",
              cli_ok and cli_loaded["edge_count"] == g["edge_count"]
              and cli_cyclic == 1,
              "graph 0 acyclic / 1 cyclic, JSON round-trips"),
    ]


DRILLS = {
    "loop": _loop_drill,
    "redact": _redact_drill,
    "trace": _trace_drill,
    "team": _team_drill,
    "router": _router_drill,
    "budget": _budget_drill,
    "stop": _stop_drill,
    "redact_nested": _redact_nested_drill,
    "audit": _audit_drill,
    "pack": _pack_drill,
    "sbom": _sbom_drill,
    "memory": _memory_drill,
    "compact": _compact_drill,
    "cache": _cache_drill,
    "hooks": _hooks_drill,
    "fanout": _fanout_drill,
    "structured": _structured_drill,
    "retry": _retry_drill,
    "breaker": _breaker_drill,
    "planner": _planner_drill,
    "snapshot": _snapshot_drill,
    "prompt": _prompt_drill,
    "jit": _jit_drill,
    "chaos": _chaos_drill,
    "chain": _chain_drill,
    "diff": _diff_drill,
    "stats": _stats_drill,
    "bench": _bench_drill,
    "fuzz": _fuzz_drill,
    "property": _property_drill,
    "pack2": _pack2_drill,
    "graph": _graph_drill,
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
