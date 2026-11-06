"""Two-role team runner: lead → handoff → specialist on ONE shared journal.

The team loop is event-sourced exactly like :class:`~openagentx.runner.AgentRunner`:
every observable action is redacted *before* journaling and carries a ``role``
tag, so a single journal holds the whole collaboration with a dense sequence
across phases. The lead delegates via the control-plane action
``{"tool": "handoff", "args": {"to": "specialist", "reason": "..."}}``.

Contracts:
- ``handoff`` is reserved: it is journaled as a ``handoff`` event (never a
  ``tool_call``), and it switches the active role. Only the lead may hand off,
  and only to the specialist.
- Stop reasons are explicit: ``reply`` | ``stop_tool`` | ``max_steps`` |
  ``script_error`` | ``handoff_rejected``.
- The specialist's history opens with the original task plus a HANDOFF
  observation, so delegated context flows through the journal, not hidden state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .events import Journal
from .llm import LLMUnavailable, ScriptExhausted, ScriptParseError
from .redact import redact_obj
from .tools import ToolRegistry, jsonable

HANDOFF_TOOL = "handoff"


@dataclass(frozen=True)
class TeamResult:
    run_id: str
    stop_reason: str
    reply: str
    handoffs: int
    steps: dict
    events: int
    journal_path: str


class TeamRunner:
    """Runs a lead→specialist pipeline against one registry and one journal."""

    ROLES = ("lead", "specialist")

    def __init__(
        self,
        lead_llm,
        specialist_llm,
        tools: ToolRegistry,
        journal_path,
        max_steps_per_role: int = 8,
        workdir: str = ".",
        run_id: str = "",
    ):
        self.llms = {"lead": lead_llm, "specialist": specialist_llm}
        self.tools = tools
        self.journal_path = str(journal_path)
        self.max_steps_per_role = int(max_steps_per_role)
        self.workdir = workdir
        self._fixed_run_id = run_id

    def run(self, task: str) -> TeamResult:
        run_id = self._fixed_run_id or uuid.uuid4().hex[:12]
        j = Journal(self.journal_path)
        j.start_run(run_id)
        j.append("run_start", {"task": str(task), "team": list(self.ROLES),
                               "max_steps_per_role": self.max_steps_per_role})

        handoffs = 0
        steps: dict = {}
        reply_text = ""
        handoff_reason = ""

        for role in self.ROLES:
            j.append("role_start", {"role": role})
            history = [{"role": "user", "content": str(task)}]
            if role != self.ROLES[0]:
                history.append({"role": "user", "content": "HANDOFF " + jsonable(
                    {"from": self.ROLES[0], "reason": handoff_reason})})
            steps[role] = 0
            handed_off = False

            while steps[role] < self.max_steps_per_role:
                j.append("step_start", {"role": role, "step": steps[role]})
                steps[role] += 1
                try:
                    turn = self.llms[role].complete(history)
                except (ScriptExhausted, ScriptParseError, LLMUnavailable) as e:
                    payload, _ = redact_obj({"role": role,
                                             "error": f"{type(e).__name__}: {e}"})
                    j.append("error", payload)
                    j.append("run_end", {"stop_reason": "script_error", "role": role})
                    return self._finish(j, run_id, "script_error", reply_text,
                                        handoffs, steps)

                thought = str(turn.get("thought", ""))
                if thought:
                    p, _ = redact_obj({"role": role, "text": thought,
                                       "step": steps[role] - 1})
                    j.append("thought", p)

                if "reply" in turn:
                    p, _ = redact_obj({"role": role, "text": str(turn["reply"])})
                    j.append("reply", p)
                    reply_text = p["text"]
                    j.append("run_end", {"stop_reason": "reply", "role": role})
                    return self._finish(j, run_id, "reply", reply_text,
                                        handoffs, steps)

                action = turn.get("action") or {}
                tool = str(action.get("tool", ""))
                args = dict(action.get("args", {}))

                if tool == HANDOFF_TOOL:
                    to = str(args.get("to", ""))
                    reason = str(args.get("reason", ""))
                    if role != self.ROLES[0] or to != self.ROLES[1]:
                        payload, _ = redact_obj({
                            "role": role,
                            "error": f"handoff rejected: {role} cannot hand off to '{to}'"})
                        j.append("error", payload)
                        j.append("run_end",
                                 {"stop_reason": "handoff_rejected", "role": role})
                        return self._finish(j, run_id, "handoff_rejected",
                                            reply_text, handoffs, steps)
                    p, _ = redact_obj({"from_role": role, "to_role": to,
                                       "reason": reason})
                    j.append("handoff", p)
                    handoffs += 1
                    handoff_reason = p["reason"]
                    handed_off = True
                    break

                if tool == "stop":
                    j.append("run_end", {"stop_reason": "stop_tool", "role": role,
                                         "reason": str(args.get("reason", ""))})
                    return self._finish(j, run_id, "stop_tool", reply_text,
                                        handoffs, steps)

                jp, n_red = redact_obj({"role": role, "tool": tool, "args": args})
                j.append("tool_call", jp)
                out = self.tools.call(tool, args)
                if out.get("ok"):
                    payload = {"role": role, "tool": tool, "ok": True,
                               "result": out.get("result", {})}
                else:
                    payload = {"role": role, "tool": tool, "ok": False,
                               "error": str(out.get("error", "unknown error"))}
                payload, n_res = redact_obj(payload)
                payload["redactions"] = n_res + n_red
                j.append("tool_result", payload)
                history.append({
                    "role": "user",
                    "content": "OBS " + jsonable(payload.get("result", payload.get("error"))),
                })

            if handed_off:
                continue
            # the role exhausted its step budget without a terminal action
            j.append("run_end", {"stop_reason": "max_steps", "role": role})
            return self._finish(j, run_id, "max_steps", reply_text,
                                handoffs, steps)

        # defensive: unreachable while the specialist cannot hand off
        j.append("run_end", {"stop_reason": "max_steps", "role": self.ROLES[-1]})
        return self._finish(j, run_id, "max_steps", reply_text, handoffs, steps)

    def _finish(self, j: Journal, run_id: str, stop_reason: str, reply: str,
                handoffs: int, steps: dict) -> TeamResult:
        return TeamResult(
            run_id=run_id,
            stop_reason=stop_reason,
            reply=reply,
            handoffs=handoffs,
            steps=dict(steps),
            events=len(j.events()),
            journal_path=self.journal_path,
        )


def team_events_summary(events: list) -> dict:
    """Role-aware aggregate over a team journal (views stay single-source)."""
    by_role: dict = {}
    for ev in events:
        role = str((ev.payload or {}).get("role", ""))
        if role:
            slot = by_role.setdefault(role, {"events": 0, "tool_calls": 0})
            slot["events"] += 1
            if ev.type == "tool_call":
                slot["tool_calls"] += 1
    return {"total": len(events), "roles": dict(sorted(by_role.items()))}
