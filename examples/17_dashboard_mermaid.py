"""Offline example 17 — dashboard + mermaid: report v2 and the causal spine.

``oax dashboard`` is report v2: a self-contained HTML page whose
counters ARE replay's numbers (one source of truth), with summary
cards, a per-type distribution, a per-tool table and the redacted,
escaped timeline — byte-deterministic, inline CSS, zero external
assets. ``oax mermaid`` exports the same journal as a deterministic
flowchart TD: one node per event, one spine edge per consecutive pair,
labels quote-escaped so the file is always valid Mermaid and a
pre-redaction journal still cannot leak a secret through a diagram.
This example runs a real scripted agent, renders both views, attacks
them (a raw token in the journal, a torn tail, an empty journal) and
re-checks every invariant the drills grade.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.dashboard import (dashboard_data, dashboard_sha256,
                                  render_dashboard)
from openagentx.events import Journal
from openagentx.llm import ScriptedLLM
from openagentx.mermaid import trace_mermaid
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-17-")

    # 1) a real scripted run: think, compute, persist, planned failure, reply
    jp = os.path.join(wd, "journal.jsonl")
    script = [
        '{"action": {"tool": "think", "args": {"note": "report on me"}}, "thought": "plan"}',
        '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
        '{"action": {"tool": "write_file", "args": {"path": "note.txt", "text": "v2"}}, "thought": "persist"}',
        '{"action": {"tool": "read_file", "args": {"path": "missing.txt"}}, "thought": "planned failure"}',
        '{"reply": "reported and diagrammed"}',
    ]
    result = AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                         workdir=wd, run_id="example-17").run("render my trace")
    if result.stop_reason != "reply":
        raise SystemExit(f"unexpected stop: {result.stop_reason}")

    # 2) dashboard: replay's numbers, byte-deterministic, self-contained
    d = dashboard_data(jp)
    if d["tool_calls"] != 4 or d["tool_fails"] != 1 or d["replies"] != 1:
        raise SystemExit(f"dashboard counters disagree with the plan: {d}")
    h1 = render_dashboard(jp)
    h2 = render_dashboard(jp)
    if h1 != h2 or dashboard_sha256(jp) != dashboard_sha256(jp):
        raise SystemExit("dashboard render is not deterministic")
    if not h1.startswith("<!doctype html>") or "http://" in h1 or "<script" in h1:
        raise SystemExit("dashboard HTML is not self-contained")
    out = os.path.join(wd, "trace.dashboard.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(h1)
    print(f"dashboard: {d['events']} events, tool_fails={d['tool_fails']}, "
          f"{len(h1)} bytes, sha256={dashboard_sha256(jp)[:16]} -> {out}")

    # 3) defense in depth: a raw token in the journal never reaches the view
    raw = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    leak = os.path.join(wd, "leak.jsonl")
    lj = Journal(leak)
    lj.start_run("leak-run")
    lj.append("thought", {"text": "token " + raw})
    h_leak = render_dashboard(leak)
    m_leak = trace_mermaid(leak)
    if raw in h_leak or raw in m_leak:
        raise SystemExit("raw token leaked through a view")
    print("defense in depth: raw token re-redacted by dashboard AND mermaid")

    # 4) mermaid: the causal spine, escaped and deterministic
    m1 = trace_mermaid(jp)
    m2 = trace_mermaid(jp)
    if m1 != m2 or not m1.startswith("flowchart TD"):
        raise SystemExit("mermaid render is not deterministic")
    events, torn = load_trace(jp)
    nodes = sum(1 for l in m1.splitlines() if l.lstrip().startswith("E") and '["' in l)
    edges = sum(1 for l in m1.splitlines() if " --> " in l)
    if nodes != len(events) or edges != len(events) - 1 or torn:
        raise SystemExit(f"spine mismatch: {nodes} nodes / {edges} edges")
    fail_ids = [f"E{e.seq:03d}" for e in events
                if e.type == "tool_result" and (e.payload or {}).get("ok") is False]
    if not any(fid in l for l in m1.splitlines() for fid in fail_ids if " fail" in l):
        raise SystemExit("the planned failure is not classed fail")
    mmd_out = os.path.join(wd, "trace.mmd")
    with open(mmd_out, "w", encoding="utf-8") as fh:
        fh.write(m1)
    print(f"mermaid: {nodes} nodes, {edges} spine edges, escaped labels"
          f" -> {mmd_out}")

    # 5) honest zero states: empty journal and torn tail
    empty = os.path.join(wd, "empty.jsonl")
    open(empty, "w", encoding="utf-8").close()
    if dashboard_data(empty)["events"] != 0 or "0 events" not in render_dashboard(empty):
        raise SystemExit("empty journal is not the honest zero state")
    if " --> " in trace_mermaid(empty):
        raise SystemExit("empty journal rendered phantom edges")
    torn_path = os.path.join(wd, "torn.jsonl")
    with open(torn_path, "wb") as fh:
        fh.write(open(jp, "rb").read() + b'{"seq": 99, "tu')
    d_torn = dashboard_data(torn_path)
    if not d_torn["torn_tail"] or d_torn["events"] != d["events"]:
        raise SystemExit("torn tail not isolated with the prefix counted")
    if "torn_tail=True" not in render_dashboard(torn_path):
        raise SystemExit("torn flag missing from the integrity strip")
    print("zero states: empty journal honest, torn tail isolated with prefix")

    print("OK 17_dashboard_mermaid (the dashboard is replay's numbers"
          " rendered byte-deterministically with zero external assets; the"
          " mermaid export chains the causal spine with escaped labels and"
          " both views re-redact — a secret can never leak through a view)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
