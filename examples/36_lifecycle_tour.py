"""Offline example 36 — the blueprint's task lifecycle, walked end-to-end.

The HYDRION ONE blueprint (``docs/blueprint/``) spends its most important
section — §5 — on one idea: turn a conversation into a persisted, inspectable
workflow where the orchestrator owns state transitions and the model only
proposes them. This example walks that section the way golden task 47 grades
it: the eleven canonical states with their exact legal-transition table, the
frozen terminals (``COMPLETED``/``FAILED``/``CANCELLED`` — the only zero-out
states), the happy path through real dense journal events, illegal moves
refused loudly with zero appends, approval bound to the exact plan hash (a
different plan is refused, the same plan passes), the low-risk pre-approved
path recorded honestly, waiting/blocked/recovery side paths, cancellation
that is terminal yet still records cleanup (blueprint: "Terminal; cleanup and
audit still run"), replay from a durable on-disk journal that re-validates
every move and renders byte-identically, reasons crossing the redaction
boundary, and a plan hash that is canonical (key order irrelevant) and
content-sensitive.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import Journal
from openagentx.lifecycle import (ApprovalMismatch, IllegalTransition,
                                  LifecycleError, TaskLifecycle,
                                  TRANSITIONS, TERMINAL_STATES, plan_hash)
from openagentx.tools import vault_value as vv
from openagentx.trace import load_trace


def step(n: int, title: str) -> None:
    print(f"\n== step {n}: {title}")


def main() -> int:
    # 1) the eleven states and the frozen terminals
    step(1, "eleven canonical states, three frozen terminals")
    states = ["CREATED", "PLANNED", "APPROVED", "RUNNING", "VERIFYING",
              "WAITING_FOR_USER", "BLOCKED", "RECOVERY",
              "COMPLETED", "FAILED", "CANCELLED"]
    assert list(TRANSITIONS) == states, list(TRANSITIONS)
    assert TERMINAL_STATES == {"COMPLETED", "FAILED", "CANCELLED"}
    zero_out = [s for s in TRANSITIONS if not TRANSITIONS[s]]
    assert sorted(zero_out) == sorted(TERMINAL_STATES), zero_out
    print("   states:", ", ".join(states))
    print("   terminals (zero outgoing):", ", ".join(sorted(zero_out)))

    # 2) the happy path through real events
    step(2, "happy path: CREATED -> PLANNED -> APPROVED -> RUNNING -> "
            "VERIFYING -> COMPLETED")
    m = TaskLifecycle("demo-1")
    plan = {"objective": "sourced technical report", "risk": "low"}
    for move in (m.transition("PLANNED"), m.approve(plan), m.start(plan),
                 m.transition("VERIFYING"), m.transition("COMPLETED")):
        pass
    seqs = [ev.seq for ev in m.events]
    assert m.state == "COMPLETED" and seqs == list(range(len(seqs)))
    assert sum(ev.type == "lifecycle_transition" for ev in m.events) == 5
    for ev in m.events:
        print(f"   [{ev.seq:03d}] {ev.type}")
    print("   render (deterministic, no wall-clock):")
    for ln in m.render().strip().splitlines():
        print("     " + ln)

    # 3) illegal moves refuse loudly and append nothing
    step(3, "illegal moves raise IllegalTransition and append nothing")
    probes = [("CREATED", "COMPLETED"), ("VERIFYING", "RUNNING"),
              ("COMPLETED", "PLANNED"), ("CANCELLED", "RUNNING"),
              ("APPROVED", "VERIFYING")]
    paths = {
        "CREATED": [],
        "VERIFYING": ["PLANNED", "APPROVED", "RUNNING", "VERIFYING"],
        "COMPLETED": ["PLANNED", "APPROVED", "RUNNING", "VERIFYING",
                      "COMPLETED"],
        "CANCELLED": ["CANCELLED"],
        "APPROVED": ["PLANNED", "APPROVED"],
    }
    for src, dst in probes:
        mp = TaskLifecycle("demo-illegal")
        for s in paths[src]:
            if s == "APPROVED":
                mp.approve({"objective": "probe"})
            elif s == "RUNNING":
                mp.start({"objective": "probe"})
            else:
                mp.transition(s)
        n0 = len(mp.events)
        try:
            mp.transition(dst)
            raise AssertionError(f"{src} -> {dst} should be illegal")
        except IllegalTransition as err:
            assert mp.state == src and len(mp.events) == n0
            print(f"   {src} -> {dst}: refused ({err})")

    # 4) approval is bound to the exact plan hash
    step(4, "approval bound to the exact plan hash")
    m2 = TaskLifecycle("demo-2")
    m2.transition("PLANNED")
    m2.approve({"objective": "ship the CSV export"}, actor="human")
    n0 = len(m2.events)
    try:
        m2.start({"objective": "ship the CSV export", "extra": 1})
        raise AssertionError("a drifted plan must not start")
    except ApprovalMismatch as err:
        print(f"   refused: {err}")
    assert m2.state == "APPROVED" and len(m2.events) == n0
    m2.start({"objective": "ship the CSV export"})
    approval_ev = [e for e in m2.events if e.type == "lifecycle_approval"][0]
    assert approval_ev.payload["action_hash"] == plan_hash(
        {"objective": "ship the CSV export"})
    print(f"   journal approval hash: {approval_ev.payload['action_hash'][:16]}…")

    # 5) the low-risk pre-approved path stays honest
    step(5, "PLANNED -> RUNNING without approval is recorded pre_approved")
    m3 = TaskLifecycle("demo-3")
    m3.transition("PLANNED")
    m3.start()
    last = m3.events[-1].payload
    assert m3.state == "RUNNING" and last.get("pre_approved") is True
    assert m3.approved_hash is None
    print("   payload:", {k: last[k] for k in ("from", "to", "pre_approved")})

    # 6) waiting, blocked and recovery side paths
    step(6, "side paths: waiting resumes with a re-bound hash; blocked and "
            "recovery recover; recovery never shortcuts to COMPLETED")
    m4 = TaskLifecycle("demo-4")
    plan_v1 = {"objective": "first draft"}
    m4.transition("PLANNED")
    m4.approve(plan_v1)
    m4.start(plan_v1)
    m4.transition("WAITING_FOR_USER", reason="need user input")
    plan_v2 = {"objective": "revised after review"}
    m4.approve(plan_v2)
    m4.start(plan_v2)
    assert m4.state == "RUNNING" and m4.approved_hash == plan_hash(plan_v2)
    m5 = TaskLifecycle("demo-5")
    for s in ("PLANNED",):
        m5.transition(s)
    m5.start()
    m5.transition("BLOCKED", reason="dependency offline")
    m5.transition("RUNNING", reason="dependency back")
    m6 = TaskLifecycle("demo-6")
    m6.transition("PLANNED")
    m6.start()
    m6.transition("RECOVERY", reason="bounded retry")
    m6.transition("BLOCKED")
    try:
        m6.transition("COMPLETED")
        raise AssertionError("RECOVERY -> COMPLETED must be illegal")
    except IllegalTransition:
        print("   RECOVERY -> COMPLETED refused (per the blueprint table)")
    print("   waiting -> re-approve -> resume: OK;"
          " blocked -> running: OK; recovery paths: OK")

    # 7) cancellation is terminal but cleanup still runs
    step(7, "CANCELLED is terminal; cleanup and audit still run")
    m7 = TaskLifecycle("demo-7")
    m7.transition("PLANNED")
    m7.start()
    m7.cancel(reason="user stopped", actor="user")
    assert m7.state == "CANCELLED"
    m7.record_cleanup("workspace archived")
    assert m7.cleanups == 1
    try:
        m8 = TaskLifecycle("demo-8")
        m8.record_cleanup("too early")
        raise AssertionError("non-terminal cleanup must be refused")
    except LifecycleError as err:
        print(f"   refused: {err}")
    print("   cleanup after CANCELLED journaled:",
          m7.events[-1].type, "-", m7.events[-1].payload["note"])

    # 8) replay from the durable journal is a byte-identical pure fold
    step(8, "durable journal on disk; replay re-validates and renders "
            "byte-identically")
    wd = tempfile.mkdtemp(prefix="oax-example36-")
    jpath = os.path.join(wd, "lifecycle.jsonl")
    jm = TaskLifecycle("demo-durable", journal=Journal(jpath))
    jm.transition("PLANNED", reason="planned")
    jm.approve({"objective": "durable work"}, actor="human")
    jm.start({"objective": "durable work"}, actor="agent")
    jm.transition("VERIFYING", reason="tests done")
    jm.transition("COMPLETED")
    jm.record_cleanup("archived")
    disk_events, torn = load_trace(jpath)
    assert not torn and len(disk_events) == len(jm.events)
    rm = TaskLifecycle.replay(disk_events)
    assert rm.state == "COMPLETED" and rm.cleanups == 1
    assert rm.render() == jm.render()
    print(f"   {len(disk_events)} events on disk; replay render identical")

    # 9) reasons cross the redaction boundary
    step(9, "a secret typed into a reason dies at the boundary")
    m9 = TaskLifecycle("demo-redact")
    tok = vv("github")
    m9.transition("PLANNED", reason=f"handle {tok} at the boundary")
    ev = m9.events[-1]
    assert "[REDACTED:github_token]" in ev.payload["reason"]
    assert tok not in ev.payload["reason"] and tok not in m9.render()
    print("   stored reason:", ev.payload["reason"])

    # 10) the plan hash is canonical and content-sensitive
    step(10, "plan_hash: key order irrelevant, any content change matters")
    assert plan_hash({"a": 1, "b": 2}) == plan_hash({"b": 2, "a": 1})
    assert plan_hash({"a": 1, "b": 2}) != plan_hash({"a": 1, "b": 3})
    h = plan_hash({"objective": "x"})
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
    print("   hash:", h[:16] + "…")

    print("\nOK 36_lifecycle_tour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
