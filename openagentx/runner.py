"""The event-sourced agent loop: think → act → observe → … → reply.

Every observable action is journaled *after* redaction — the journal stores
redacted truth, tools execute on real values. Stop reasons are explicit:
``reply`` | ``stop_tool`` | ``max_steps`` | ``script_error`` |
``model_unavailable``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from .events import Journal
from .hooks import ALLOW, DENY
from .llm import LLMUnavailable, ScriptExhausted, ScriptParseError
from .redact import redact_obj
from .tools import ToolRegistry, jsonable

RESERVED_TOOLS = {"stop"}


@dataclass(frozen=True)
class RunResult:
    run_id: str
    stop_reason: str
    steps: int
    reply: str
    events: int
    journal_path: str


class AgentRunner:
    """Runs one agent turn-loop against a registry, journaling everything."""

    def __init__(
        self,
        llm,
        tools: ToolRegistry,
        journal_path,
        max_steps: int = 8,
        max_tool_calls: int = 0,
        workdir: str = ".",
        run_id: str = "",
        hooks=None,
    ):
        self.llm = llm
        self.tools = tools
        self.journal_path = str(journal_path)
        self.max_steps = int(max_steps)
        self.max_tool_calls = int(max_tool_calls)
        self.workdir = workdir
        self._fixed_run_id = run_id
        self.hooks = hooks

    def run(self, task: str) -> RunResult:
        run_id = self._fixed_run_id or uuid.uuid4().hex[:12]
        j = Journal(self.journal_path)
        j.start_run(run_id)

        history: list = [{"role": "user", "content": task}]
        steps = 0
        tool_calls_used = 0
        reply_text = ""

        j.append("run_start", {"task": str(task), "max_steps": self.max_steps,
                               "max_tool_calls": self.max_tool_calls})

        stop_reason = "max_steps"
        while steps < self.max_steps:
            j.append("step_start", {"step": steps})
            steps += 1
            try:
                turn = self.llm.complete(history)
            except (ScriptExhausted, ScriptParseError) as e:
                payload, _ = redact_obj({"error": f"{type(e).__name__}: {e}"})
                j.append("error", payload)
                j.append("run_end", {"stop_reason": "script_error"})
                stop_reason = "script_error"
                break
            except LLMUnavailable as e:
                payload, _ = redact_obj({"error": f"{type(e).__name__}: {e}"})
                j.append("error", payload)
                j.append("run_end", {"stop_reason": "model_unavailable"})
                stop_reason = "model_unavailable"
                break

            thought = turn.get("thought", "")
            if thought:
                p, _ = redact_obj({"text": str(thought), "step": steps - 1})
                j.append("thought", p)

            if "reply" in turn:
                p, _ = redact_obj({"text": str(turn["reply"])})
                j.append("reply", p)
                reply_text = p["text"]
                j.append("run_end", {"stop_reason": "reply"})
                stop_reason = "reply"
                break

            action = turn.get("action") or {}
            tool = str(action.get("tool", ""))
            args = dict(action.get("args", {}))

            if tool in RESERVED_TOOLS:
                j.append("run_end", {
                    "stop_reason": "stop_tool",
                    "reason": str(args.get("reason", "")),
                })
                stop_reason = "stop_tool"
                break

            if self.max_tool_calls and tool_calls_used >= self.max_tool_calls:
                j.append("budget", {
                    "kind": "tool_calls",
                    "used": tool_calls_used,
                    "cap": self.max_tool_calls,
                    "rejected_tool": tool,
                })
                j.append("run_end", {"stop_reason": "budget",
                                     "cap": self.max_tool_calls})
                stop_reason = "budget"
                break

            # hook policy: every decision is journaled; a denied call never
            # reaches the registry (no tool_call, no tool_result, no effects)
            decision, deny_reason = ALLOW, ""
            if self.hooks is not None:
                decision, deny_reason = self.hooks.decide(tool, args)
                j.append("hook", {"tool": tool, "decision": decision,
                                  "reason": deny_reason})
            if decision == DENY:
                history.append({"role": "user",
                                "content": f"DENY {tool}: {deny_reason}"})
                continue

            jp, n_red = redact_obj({"tool": tool, "args": args})
            j.append("tool_call", jp)
            tool_calls_used += 1

            out = self.tools.call(tool, args)
            if out.get("ok"):
                payload = {"tool": tool, "ok": True,
                           "result": out.get("result", {})}
            else:
                payload = {"tool": tool, "ok": False,
                           "error": str(out.get("error", "unknown error"))}
            payload, n_res = redact_obj(payload)
            payload["redactions"] = n_res + n_red
            j.append("tool_result", payload)
            history.append({
                "role": "user",
                "content": "OBS " + jsonable(payload.get("result", payload.get("error"))),
            })
        else:
            j.append("run_end", {"stop_reason": "max_steps"})

        events = j.events()
        return RunResult(
            run_id=run_id,
            stop_reason=stop_reason,
            steps=steps,
            reply=reply_text,
            events=len(events),
            journal_path=self.journal_path,
        )


def replay_script(llm, tools, task: str, max_steps: int = 8, workdir: str = "."):
    """Convenience: run with a fresh journal in *workdir*; returns RunResult."""
    import os

    path = os.path.join(workdir, "journal.jsonl")
    return AgentRunner(llm, tools, path, max_steps=max_steps, workdir=workdir).run(task)


def events_summary(events: list) -> dict:
    """Aggregate counters from an event list (used by trace views)."""
    types: dict = {}
    for ev in events:
        types[ev.type] = types.get(ev.type, 0) + 1
    return {"total": len(events), "types": dict(sorted(types.items()))}


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)
