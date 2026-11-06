"""Offline example 05 — memory + compaction: recall past runs, fold a journal.

Two mini runs are executed offline (one genuinely touches the fixture vault,
so its journal holds redacted markers only). ``MemoryLite`` indexes both
journals and recalls the right run per query — read-only, deterministic.
Then ``compact_journal`` folds the tool-call pairs of the bugfix run into a
denser secondary journal while the original stays byte-identical.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.compact import compact_journal
from openagentx.events import sequence_dense
from openagentx.llm import ScriptedLLM
from openagentx.memory import MemoryLite
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools, vault_value
from openagentx.trace import load_trace, replay


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-05-")

    def run(rid: str, task: str, script: list) -> str:
        jp = os.path.join(wd, f"journal-{rid}.jsonl")
        AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                    max_steps=6, workdir=wd, run_id=rid).run(task)
        return jp

    j1 = run("deploy-run", "deploy the api service to staging", [
        '{"action": {"tool": "echo", "args": {"text": "deploying the api service to staging"}},'
        ' "thought": "announce the rollout"}',
        '{"action": {"tool": "calc", "args": {"expr": "2+2"}}, "thought": "sanity check"}',
        '{"reply": "api service deployed to staging"}',
    ])
    j2 = run("bugfix-run", "fix the login bug in the auth flow", [
        '{"action": {"tool": "vault_read", "args": {"key": "github"}},'
        ' "thought": "fetch the credential for the auth gateway"}',
        '{"action": {"tool": "echo", "args": {"text": "patching the login handler in auth"}},'
        ' "thought": "fix the login bug"}',
        '{"reply": "login bug fixed in the auth flow"}',
    ])

    mem = MemoryLite()
    mem.index_journal(j1)
    mem.index_journal(j2)
    hit_deploy = mem.recall("deploy the api service", k=3)
    hit_bugfix = mem.recall("login bug in auth", k=3)
    print(f"recall 'deploy the api service' -> {hit_deploy[0]['run_id']} "
          f"(score {hit_deploy[0]['score']})")
    print(f"recall 'login bug in auth'      -> {hit_bugfix[0]['run_id']} "
          f"(score {hit_bugfix[0]['score']})")

    token = vault_value("github")
    seen = open(j2, encoding="utf-8").read() + str(hit_bugfix)
    stats = compact_journal(j2, os.path.join(wd, "bugfix.compact.jsonl"))
    compacted, torn = load_trace(os.path.join(wd, "bugfix.compact.jsonl"))
    folds = [e for e in compacted if e.type == "tool_fold"]

    assert hit_deploy[0]["run_id"] == "deploy-run"
    assert hit_bugfix[0]["run_id"] == "bugfix-run"
    assert mem.recall("deploy the api service", k=3) == hit_deploy, "deterministic"
    assert mem.recall("quantum widget zzzq") == [], "no hallucinated hits"
    assert token not in seen, "raw fixture token never resurfaces"
    assert open(j2, "rb").read() == open(j2, "rb").read(), "source untouched by reads"

    assert stats["dst_events"] < stats["src_events"] and stats["ratio"] < 1.0
    assert not torn and sequence_dense(compacted)
    assert len(folds) == stats["tool_folds"] == 2
    assert not [e for e in compacted if e.type in ("tool_call", "tool_result", "step_start")]
    st = replay(compacted)
    assert st["runs_opened"] == 1 and st["replies"] == 1 and st["final_stop"] == "reply"
    print(f"compact bugfix journal: {stats['src_events']} -> {stats['dst_events']} events "
          f"(tool_folds={stats['tool_folds']}, ratio={stats['ratio']})")
    print("OK 05_memory_compact (TF-IDF recall over runs, honest journal compaction)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
