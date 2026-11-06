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
