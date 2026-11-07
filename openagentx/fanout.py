"""Parallel fan-out: one task, N branches, one coordination journal.

A coordinator dispatches the task (or per-branch tasks) to N named branch
agents. Every branch is a *real* :class:`~openagentx.runner.AgentRunner` run
with its own journal; the parent journal references each branch by name,
journal path and run_id, records every branch outcome — including honest
failures — then fans in and lets the coordinator answer.

Contracts:
- Dispatch order is the branch insertion order (deterministic); with fixed
  run_ids a re-run is structurally identical (same seq/type/payload stream).
- A failing branch never aborts the fan-in: its ``script_error`` (or any
  other stop reason) is recorded in ``branch_end`` and flows into ``fanin``
  with an empty reply — failures are data, not crashes.
- The coordinator sees every branch reply as an observation and replies on
  the parent journal under ``role: "coordinator"``.
- Everything is redacted before journaling, exactly like the team loop.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from .events import Journal
from .llm import LLMUnavailable, ScriptExhausted, ScriptParseError
from .redact import redact_obj
from .runner import AgentRunner
from .tools import ToolRegistry


@dataclass(frozen=True)
class BranchResult:
    name: str
    run_id: str
    stop_reason: str
    reply: str
    steps: int
    events: int
    journal_path: str


@dataclass(frozen=True)
class FanoutResult:
    run_id: str
    stop_reason: str
    reply: str
    branches: list
    events: int
    journal_path: str


def _safe_name(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(name))


class FanoutRunner:
    """Dispatch one task to N branch agents, then fan in on one journal."""

    def __init__(
        self,
        coordinator_llm,
        branch_llms: dict,
        tools: ToolRegistry,
        journal_path,
        workdir: str = ".",
        run_id: str = "",
        max_steps_per_branch: int = 6,
        branch_tasks: dict = None,
    ):
        self.coordinator = coordinator_llm
        self.branch_llms = dict(branch_llms)  # insertion order = dispatch order
        self.tools = tools
        self.journal_path = str(journal_path)
        self.workdir = workdir
        self._fixed_run_id = run_id
        self.max_steps_per_branch = int(max_steps_per_branch)
        self.branch_tasks = dict(branch_tasks or {})

    def run(self, task: str) -> FanoutResult:
        run_id = self._fixed_run_id or uuid.uuid4().hex[:12]
        j = Journal(self.journal_path)
        j.start_run(run_id)
        j.append("run_start", {
            "task": str(task),
            "mode": "fanout",
            "branches": list(self.branch_llms.keys()),
            "max_steps_per_branch": self.max_steps_per_branch,
        })

        branch_results: list = []
        for name, llm in self.branch_llms.items():
            safe = _safe_name(name)
            btask = str(self.branch_tasks.get(name, task))
            bname = f"branch-{safe}.jsonl"  # relative: journals stay portable
            bjp = os.path.join(self.workdir, bname)
            j.append("branch_start", {"branch": str(name), "journal": bname,
                                      "task": btask})
            r = AgentRunner(
                llm, self.tools, bjp,
                max_steps=self.max_steps_per_branch,
                workdir=self.workdir,
                run_id=f"{run_id}-{safe}",
            ).run(btask)
            j.append("branch_end", {
                "branch": str(name),
                "run_id": r.run_id,
                "stop_reason": r.stop_reason,
                "reply": r.reply,
                "steps": r.steps,
                "events": r.events,
            })
            branch_results.append(BranchResult(
                name=str(name), run_id=r.run_id, stop_reason=r.stop_reason,
                reply=r.reply, steps=r.steps, events=r.events,
                journal_path=bjp))

        replies = {b.name: b.reply for b in branch_results}
        stop_reasons = {b.name: b.stop_reason for b in branch_results}
        j.append("fanin", {"branches": len(branch_results),
                           "replies": replies,
                           "stop_reasons": stop_reasons})

        j.append("role_start", {"role": "coordinator"})
        history = [{"role": "user", "content": str(task)}]
        for b in branch_results:
            history.append({"role": "user",
                            "content": f"BRANCH {b.name} ({b.stop_reason}): {b.reply}"})
        try:
            turn = self.coordinator.complete(history)
        except (ScriptExhausted, ScriptParseError, LLMUnavailable) as e:
            payload, _ = redact_obj({"role": "coordinator",
                                     "error": f"{type(e).__name__}: {e}"})
            j.append("error", payload)
            j.append("run_end", {"stop_reason": "script_error",
                                 "role": "coordinator"})
            return self._finish(j, run_id, "script_error", "", branch_results)

        thought = str(turn.get("thought", ""))
        if thought:
            p, _ = redact_obj({"role": "coordinator", "text": thought})
            j.append("thought", p)
        if "reply" in turn:
            p, _ = redact_obj({"role": "coordinator", "text": str(turn["reply"])})
            j.append("reply", p)
            j.append("run_end", {"stop_reason": "reply", "role": "coordinator"})
            return self._finish(j, run_id, "reply", p["text"], branch_results)

        # a coordinator turn without a reply is a script contract violation
        payload, _ = redact_obj({"role": "coordinator",
                                 "error": "coordinator turn needs a reply"})
        j.append("error", payload)
        j.append("run_end", {"stop_reason": "script_error",
                             "role": "coordinator"})
        return self._finish(j, run_id, "script_error", "", branch_results)

    def _finish(self, j: Journal, run_id: str, stop_reason: str, reply: str,
                branches: list) -> FanoutResult:
        return FanoutResult(
            run_id=run_id,
            stop_reason=stop_reason,
            reply=reply,
            branches=list(branches),
            events=len(j.events()),
            journal_path=self.journal_path,
        )


def fanout_fingerprint(events: list) -> list:
    """Structural identity of a journal: everything except wall-clock ts."""
    return [(e.seq, e.run_id, e.type,
             json_dumps(e.payload)) for e in events]


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)
