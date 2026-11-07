"""Planner-executor: one planning turn, N real executor runs, one journal.

The classic plan-and-execute pattern, offline-deterministic:

- **plan turn**: the planner adapter answers with a JSON plan
  (``{"steps": ["...", "..."]}``). The raw text is parsed with
  :func:`~openagentx.structured.parse_json_loose` (fenced JSON and trailing
  commas are repaired, with notes) and validated against a strict schema —
  a plan that does not parse, does not validate, or exceeds
  ``max_plan_steps`` is a *plan bug*: it journals an honest ``error`` and
  stops ``script_error``. Bugs are never laundered into empty plans.
- **executor turns**: every plan step is executed by a *real*
  :class:`~openagentx.runner.AgentRunner` with its own journal (``step-XX``
  files). A failing step never aborts the plan: its stop reason and empty
  reply are recorded in ``step_end`` and flow into ``plan_done`` — failures
  are data, not crashes. A step without a matching executor adapter is
  recorded as ``executor_missing`` the same way.
- **summary turn**: the planner sees every step outcome and closes the run
  with a reply on the parent journal.

With fixed run_ids a re-run is structurally identical (same
seq/type/payload stream), because ``step_start`` stores the *relative*
journal name. Everything is redacted before journaling.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from .events import Journal
from .llm import LLMUnavailable, ScriptExhausted, ScriptParseError
from .redact import redact_obj
from .runner import AgentRunner
from .structured import parse_json_loose, validate_schema
from .tools import ToolRegistry

PLAN_SCHEMA = {
    "type": "object",
    "required": ["steps"],
    "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
}


@dataclass(frozen=True)
class StepResult:
    index: int
    step: str
    run_id: str
    stop_reason: str
    reply: str
    steps: int
    events: int
    journal_path: str


@dataclass(frozen=True)
class PlanResult:
    run_id: str
    stop_reason: str
    reply: str
    plan: list
    steps: list
    events: int
    journal_path: str


def _safe_name(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(name))


class PlannerExecutor:
    """Plan once, execute every step with a real sub-agent, then summarize."""

    def __init__(
        self,
        planner_llm,
        step_llms: list,
        tools: ToolRegistry,
        journal_path,
        workdir: str = ".",
        run_id: str = "",
        max_steps_per_step: int = 6,
        max_plan_steps: int = 8,
    ):
        self.planner = planner_llm
        self.step_llms = list(step_llms)  # index i executes plan step i
        self.tools = tools
        self.journal_path = str(journal_path)
        self.workdir = workdir
        self._fixed_run_id = run_id
        self.max_steps_per_step = int(max_steps_per_step)
        self.max_plan_steps = int(max_plan_steps)

    def run(self, task: str) -> PlanResult:
        run_id = self._fixed_run_id or uuid.uuid4().hex[:12]
        j = Journal(self.journal_path)
        j.start_run(run_id)
        j.append("run_start", {
            "task": str(task),
            "mode": "planner",
            "executors": len(self.step_llms),
            "max_steps_per_step": self.max_steps_per_step,
            "max_plan_steps": self.max_plan_steps,
        })

        plan, step_results = self._plan_turn(j, run_id, str(task))
        if plan is None:
            return self._finish(j, run_id, "script_error", "", [], [])
        step_results = self._execute_steps(j, run_id, plan)

        replies = [s.reply for s in step_results]
        stops = [s.stop_reason for s in step_results]
        j.append("plan_done", {"steps": len(step_results),
                               "replies": replies,
                               "stop_reasons": stops})

        return self._summary_turn(j, run_id, str(task), plan, step_results)

    # ---- plan turn -------------------------------------------------------

    def _plan_turn(self, j: Journal, run_id: str, task: str):
        """Ask the planner for a validated plan; returns (steps, [])."""
        j.append("role_start", {"role": "planner"})
        try:
            turn = self.planner.complete(
                [{"role": "user", "content": f"plan: {task}"}])
        except (ScriptExhausted, ScriptParseError, LLMUnavailable) as e:
            self._fail(j, f"planner turn failed: {type(e).__name__}: {e}")
            return None, []

        raw = str(turn.get("reply", ""))
        thought = str(turn.get("thought", ""))
        if thought:
            p, _ = redact_obj({"role": "planner", "text": thought})
            j.append("thought", p)
        p, _ = redact_obj({"role": "planner", "text": raw})
        j.append("thought", p)

        value, notes = parse_json_loose(raw)
        problems = validate_schema(value, PLAN_SCHEMA) if value is not None \
            else ["plan is not JSON"]
        if not problems and (not isinstance(value, dict)
                             or not isinstance(value.get("steps"), list)):
            problems = ["plan needs a steps array"]
        if not problems and len(value["steps"]) > self.max_plan_steps:
            problems = [f"plan has {len(value['steps'])} steps, "
                        f"max_plan_steps is {self.max_plan_steps}"]
        if problems:
            payload, _ = redact_obj({"role": "planner",
                                     "error": "plan rejected",
                                     "problems": problems, "notes": notes})
            j.append("error", payload)
            j.append("run_end", {"stop_reason": "script_error",
                                 "role": "planner"})
            return None, []

        steps = [str(s) for s in value["steps"]]
        j.append("plan", {"steps": steps, "notes": notes})
        return steps, []

    # ---- executor turns ----------------------------------------------------

    def _execute_steps(self, j: Journal, run_id: str, plan: list) -> list:
        results: list = []
        for i, step in enumerate(plan):
            sname = f"step-{i:02d}-{_safe_name(step[:24])}.jsonl"
            sjp = os.path.join(self.workdir, sname)  # absolute on disk only
            j.append("step_start", {"index": i, "step": str(step),
                                    "journal": sname})
            if i >= len(self.step_llms):
                j.append("step_end", {"index": i, "run_id": "",
                                      "stop_reason": "executor_missing",
                                      "reply": "", "steps": 0, "events": 0})
                results.append(StepResult(
                    index=i, step=str(step), run_id="",
                    stop_reason="executor_missing", reply="",
                    steps=0, events=0, journal_path=sjp))
                continue
            r = AgentRunner(
                self.step_llms[i], self.tools, sjp,
                max_steps=self.max_steps_per_step,
                workdir=self.workdir,
                run_id=f"{run_id}-s{i:02d}",
            ).run(str(step))
            j.append("step_end", {
                "index": i,
                "run_id": r.run_id,
                "stop_reason": r.stop_reason,
                "reply": r.reply,
                "steps": r.steps,
                "events": r.events,
            })
            results.append(StepResult(
                index=i, step=str(step), run_id=r.run_id,
                stop_reason=r.stop_reason, reply=r.reply,
                steps=r.steps, events=r.events, journal_path=sjp))
        return results

    # ---- summary turn ------------------------------------------------------

    def _summary_turn(self, j: Journal, run_id: str, task: str, plan: list,
                      step_results: list) -> PlanResult:
        j.append("role_start", {"role": "planner"})
        history = [{"role": "user", "content": f"plan: {task}"},
                   {"role": "user", "content": f"plan: {plan}"}]
        for s in step_results:
            history.append({"role": "user",
                            "content": f"STEP {s.index} ({s.stop_reason}): {s.reply}"})
        try:
            turn = self.planner.complete(history)
        except (ScriptExhausted, ScriptParseError, LLMUnavailable) as e:
            self._fail(j, f"planner summary failed: {type(e).__name__}: {e}")
            return self._finish(j, run_id, "script_error", "", plan, step_results)
        thought = str(turn.get("thought", ""))
        if thought:
            p, _ = redact_obj({"role": "planner", "text": thought})
            j.append("thought", p)
        if "reply" in turn:
            p, _ = redact_obj({"role": "planner", "text": str(turn["reply"])})
            j.append("reply", p)
            j.append("run_end", {"stop_reason": "reply", "role": "planner"})
            return self._finish(j, run_id, "reply", p["text"], plan,
                                step_results)
        # a summary turn without a reply is a script contract violation
        self._fail(j, "planner summary turn needs a reply")
        return self._finish(j, run_id, "script_error", "", plan, step_results)

    def _fail(self, j: Journal, why: str) -> None:
        payload, _ = redact_obj({"role": "planner", "error": why})
        j.append("error", payload)
        j.append("run_end", {"stop_reason": "script_error", "role": "planner"})

    def _finish(self, j: Journal, run_id: str, stop_reason: str, reply: str,
                plan: list, steps: list) -> PlanResult:
        return PlanResult(
            run_id=run_id,
            stop_reason=stop_reason,
            reply=reply,
            plan=list(plan),
            steps=list(steps),
            events=len(j.events()),
            journal_path=self.journal_path,
        )
