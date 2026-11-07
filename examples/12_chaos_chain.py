"""Offline example 12 — chaos + hash chain: combined faults in one run, and
a journal where every line is committed.

``ChaosLLM`` and ``ChaosTools`` inject a *combined* fault plan into a single
run — two model outages and first-call tool faults at the same time — while
``RetryLLM`` recovers the outages on its deterministic schedule. Every
injection is ledgered; faulted tool calls never reach the registry, so a
faulted write leaves no file behind. The run's journal is written by
``ChainedJournal``: each line commits ``{prev, digest}`` over the full
event JSON, so the pristine journal seals cleanly — and editing a single
payload byte breaks the chain at exactly that line.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.chain import ChainError, ChainedJournal, seal, verify_journal
from openagentx.chaos import ChaosLLM, ChaosTools, chaos_summary
from openagentx.llm import ScriptedLLM
from openagentx.retry import BackoffPolicy, RetryLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-12-")
    script = [
        '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
        '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "again"}',
        '{"action": {"tool": "write_file", "args": {"path": "out.txt", "text": "survived"}}, "thought": "persist"}',
        '{"action": {"tool": "write_file", "args": {"path": "out.txt", "text": "survived"}}, "thought": "persist again"}',
        '{"reply": "chaos survived"}',
    ]

    # 1) combined chaos in ONE run: outages at LLM calls 2 and 5, tool faults
    llm = ChaosLLM(ScriptedLLM(script), {2: "net split", 5: "provider blip"})
    tools = ChaosTools(builtin_tools(wd), {"calc": 1, "write_file": 1})
    retry = RetryLLM(llm, BackoffPolicy(max_attempts=3))
    jp = os.path.join(wd, "journal.jsonl")
    res = AgentRunner(retry,
                      tools, jp, max_steps=8, workdir=wd,
                      run_id="chaos-demo", journal_cls=ChainedJournal).run(
                          "finish despite combined chaos")
    print(f"chaos: stop={res.stop_reason} reply={res.reply!r}")
    print(f"chaos: llm ledger={llm.injected}")
    print(f"chaos: tool ledger={tools.injected}")
    print(f"chaos: summary={chaos_summary(llm.injected + tools.injected)}")

    assert res.stop_reason == "reply" and res.reply == "chaos survived"
    assert [e["call"] for e in llm.injected] == [2, 5]
    assert [e["tool"] for e in tools.injected] == ["calc", "write_file"]
    assert [a["ok"] for a in retry.attempts] == [
        True, False, True, True, False, True, True], "retry scars visible"
    assert os.path.exists(os.path.join(wd, "out.txt")), "real write landed"

    # 2) zero side effects: a faulted write never touches the filesystem
    wd2 = tempfile.mkdtemp(prefix="oax-example-12b-")
    ghost_tools = ChaosTools(builtin_tools(wd2), {"write_file": 1})
    AgentRunner(ChaosLLM(ScriptedLLM([
        '{"action": {"tool": "write_file", "args": {"path": "ghost.txt", "text": "x"}}}',
        '{"reply": "done"}']), {}), ghost_tools,
        os.path.join(wd2, "j.jsonl"), max_steps=4, workdir=wd2,
        run_id="ghost").run("ghost probe")
    assert not os.path.exists(os.path.join(wd2, "ghost.txt"))
    print("chaos: faulted write left no file (zero side effects)")

    # 3) the chained journal seals cleanly
    report = verify_journal(jp)
    head = seal(jp)
    print(f"chain: {report['n']} events chained={report['chained']} "
          f"head={head[:16]}…")
    assert report["ok"] and report["chained"] and head == report["head"]

    # 4) one edited payload byte breaks the chain at exactly that line
    lines = open(jp, encoding="utf-8").read().splitlines()
    k = next(i for i, ln in enumerate(lines)
             if json.loads(ln)["type"] == "tool_call")
    tampered = list(lines)
    obj = json.loads(tampered[k])
    obj["payload"]["args"]["expr"] = "0"
    tampered[k] = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    bad = os.path.join(wd, "tampered.jsonl")
    open(bad, "w", encoding="utf-8").write("\n".join(tampered) + "\n")
    r = verify_journal(bad)
    print(f"chain: tampered line {k} -> ok={r['ok']} broken_at={r['broken_at']}")
    assert not r["ok"] and r["broken_at"] == k, "edit localized"
    try:
        seal(bad)
        raise SystemExit("seal accepted tampered bytes")
    except ChainError as e:
        print(f"chain: seal refused: {e}")

    print("OK 12_chaos_chain (combined faults recovered with an honest"
          " ledger; tampered journals localize the edit and refuse to seal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
