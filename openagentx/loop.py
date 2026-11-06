"""X-Loop: the agent kernel — perceive → decide → act → observe, with hooks.

Deliberately tiny. Lessons from the reference analysis shaped it:

* **No monolith** (agent-zero's ``monologue()`` drift): every phase is a
  pure function or a named hook; nothing mutates state mid-stream.
* **Event-sourced** (OpenHands): each iteration emits an
  ``EventEnvelope`` before doing anything.
* **Degeneracy guard** (MIRA): pathological repetition is detected and the
  run is stopped *before* more tokens are burned.
* **Budget-first** (OpenAgent-X): each iteration claims headroom first.

The model contract is a plain **text protocol** that works with ANY model —
no function-calling dependency. The model answers with either:

```json
{"action": {"tool": "tool_name", "args": {…}}, "thought": "why"}
```

or, when the task is done:

```json
{"reply": "final answer for the human"}
```

The kernel extracts the last JSON object from the response, validates it,
and dispatches tools through the registry + policy engine.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from openagentx.budget import Budget, BudgetExceededError, BudgetLedger
from openagentx.events import Actor, EventType
from openagentx.llm import LLM, LLMResponse
from openagentx.trace import TraceLog

RUN_DONE = "run.done"
RUN_FAILED = "run.failed"

BeforeIteration = Callable[[int], None]
AfterIteration = Callable[[int, "IterationResult"], None]


@dataclass
class IterationResult:
    """What happened in one loop iteration."""

    index: int
    model: str
    thought: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    observation: str | None = None
    reply: str | None = None
    tokens: int = 0


@dataclass
class RunResult:
    """Terminal outcome of :meth:`AgentKernel.run`."""

    status: str                 # done | failed | budget_exceeded | degeneracy
    reply: str
    iterations: int
    usage: dict[str, Any]
    model: str
    trace_file: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == RUN_DONE


_JSON = json.JSONDecoder()


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract the last JSON object embedded in a model response.

    Models are noisy: explanations, code fences, trailing prose. We scan
    every ``{`` from the left, decode with :meth:`json.JSONDecoder.raw_decode`
    (which respects balanced/nested braces), and keep the object that ends
    **last** — so an outer ``{"action": {"tool": …}}`` beats its inner
    ``{"tool": …}`` fragment. ``None`` means "no parsable action".
    """
    best: tuple[int, dict[str, Any]] | None = None  # (end_index, object)
    for idx in range(len(text)):
        if text[idx] != "{":
            continue
        if best is not None and idx >= best[0]:
            continue  # inside the already-parsed object
        try:
            obj, end = _JSON.raw_decode(text, idx)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and (best is None or end > best[0]):
            best = (end, obj)
    return best[1] if best else None


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


class AgentKernel:
    """The loop. Compose it; do not subclass it into a framework.

    Args:
        llm: any :class:`openagentx.llm.LLM` (EchoLLM, OpenAICompatLLM, RouterLLM…).
        trace: the run's event log.
        tools: optional ``ToolRegistry`` (Part: X-Tools). ``None`` = reply-only mode.
        budget: hard ceilings (X-Budget).
        system_prompt: optional system text; a competent default is provided.
        memory_context: optional recalled-memory string injected into context.
        on_before_iteration / on_after_iteration: observability hooks — they
            must not mutate the loop.
    """

    def __init__(
        self,
        llm: LLM,
        trace: TraceLog,
        *,
        tools: Any | None = None,
        budget: Budget | None = None,
        system_prompt: str | None = None,
        memory_context: str | None = None,
        on_before_iteration: BeforeIteration | None = None,
        on_after_iteration: AfterIteration | None = None,
        task_id: str | None = None,
    ) -> None:
        self.llm = llm
        self.trace = trace
        self.tools = tools
        self.budget = budget or Budget()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.memory_context = memory_context
        self.on_before_iteration = on_before_iteration
        self.on_after_iteration = on_after_iteration
        self.task_id = task_id

    # ------------------------------------------------------------------ public

    def run(self, task: str) -> RunResult:
        """Execute one task to completion under budget, policy, and guard."""
        ledger = BudgetLedger(budget=self.budget)
        transcript: list[dict[str, str]] = []
        recent_texts: list[str] = []

        self.trace.append(
            EventType.TASK_CREATED, task_id=self.task_id, task=task, actor_type="user", actor_id="human"
        )
        self.trace.append(
            EventType.AGENT_STARTED,
            task_id=self.task_id,
            actor_type="agent",
            actor_id="kernel",
            budget=self.budget.to_dict(),
        )

        final_reply = ""
        terminal_status = RUN_FAILED

        try:
            while True:
                iteration = ledger.next_iteration()  # raises BudgetExceededError
                if self.on_before_iteration:
                    self.on_before_iteration(iteration)

                self.trace.append(
                    EventType.KERNEL_ITERATION,
                    task_id=self.task_id,
                    actor_type="agent",
                    actor_id="kernel",
                    iteration=iteration,
                    **ledger.to_payload(),
                )

                response = self.llm.complete(
                    self._build_messages(task, transcript),
                    max_tokens=self.budget.response_reserve_tokens * 4,
                )
                ledger.charge(response)
                self.trace.append(
                    EventType.AGENT_MODEL_SELECTED,
                    task_id=self.task_id,
                    actor_type="agent",
                    actor_id="kernel",
                    model=response.model,
                    capability=getattr(self.llm, "last_profile", None) is not None,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                    },
                )

                parsed = extract_json_object(response.text)
                thought = (parsed or {}).get("thought")

                # ---- degeneracy guard: stop repetition before it costs ----
                recent_texts.append(response.text)
                if self._is_degenerate(recent_texts):
                    self.trace.append(
                        EventType.KERNEL_DEGENERACY,
                        task_id=self.task_id,
                        actor_type="policy",
                        actor_id="degeneracy-guard",
                        recent_responses=len(recent_texts),
                    )
                    terminal_status = "degeneracy"
                    final_reply = "Run stopped: the model repeated itself (degeneracy guard)."
                    break

                result = IterationResult(
                    index=iteration, model=response.model, thought=thought,
                    tokens=response.usage.total_tokens,
                )

                if parsed and "reply" in parsed:
                    result.reply = str(parsed["reply"])
                    terminal_status = RUN_DONE
                    final_reply = result.reply
                    self._record(transcript, "assistant", response.text)
                    self._after(iteration, result)
                    break

                if parsed and "action" in parsed and isinstance(parsed["action"], dict):
                    tool_name = str(parsed["action"].get("tool", ""))
                    tool_args = dict(parsed["action"].get("args") or {})
                    result.tool_name, result.tool_args = tool_name, tool_args
                    self._record(transcript, "assistant", response.text)

                    observation = self._dispatch(tool_name, tool_args)
                    result.observation = observation
                    ledger.charge_tool_call()
                    self._record(transcript, "user", f"[observation:{tool_name}] {observation}")
                else:
                    # No parsable protocol message — nudge the model once per miss.
                    self._record(transcript, "assistant", response.text)
                    observation = (
                        "[protocol-error] Respond with exactly one JSON object: "
                        '{"action": {"tool": name, "args": {…}}, "thought": "…"} '
                        'or {"reply": "…"}.'
                    )
                    result.observation = observation
                    self._record(transcript, "user", observation)

                self._after(iteration, result)
        except BudgetExceededError as exc:
            self.trace.append(
                EventType.KERNEL_BUDGET_EXCEEDED,
                task_id=self.task_id,
                actor_type="policy",
                actor_id="budget",
                ceiling=exc.ceiling,
                detail=exc.detail,
            )
            terminal_status = "budget_exceeded"
            final_reply = f"Run stopped by budget: {exc.ceiling} ({exc.detail})."

        event = EventType.TASK_COMPLETED if terminal_status == RUN_DONE else EventType.TASK_FAILED
        self.trace.append(
            event,
            task_id=self.task_id,
            actor_type="agent",
            actor_id="kernel",
            status=terminal_status,
            iterations=ledger.iterations,
            usage=ledger.to_payload()["usage"],
        )
        self.trace.append(
            EventType.KERNEL_STOPPED,
            task_id=self.task_id,
            actor_type="system",
            actor_id="kernel",
            ledger=ledger.to_payload(),
        )
        model = "unknown"
        if hasattr(self.llm, "model"):
            model = str(self.llm.model)
        elif getattr(self.llm, "last_profile", None) is not None:
            model = str(self.llm.last_profile.name)  # type: ignore[union-attr]
        return RunResult(
            status=terminal_status,
            reply=final_reply,
            iterations=ledger.iterations,
            usage=ledger.to_payload()["usage"],
            model=model,
            trace_file=str(self.trace.path),
        )

    # ----------------------------------------------------------------- private

    def _dispatch(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        """Send one tool call through the registry's single choke point."""
        self.trace.append(
            EventType.AGENT_TOOL_CALL_STARTED,
            task_id=self.task_id,
            actor_type="agent",
            actor_id="kernel",
            tool=tool_name,
            args=tool_args,
        )
        if self.tools is None:
            observation = "[error] no tool registry attached (reply-only mode)"
        else:
            observation = self.tools.dispatch(tool_name, tool_args, task_id=self.task_id)
        self.trace.append(
            EventType.AGENT_TOOL_CALL_COMPLETED,
            task_id=self.task_id,
            actor_type="runtime",
            actor_id=tool_name or "unknown",
            tool=tool_name,
            ok=not observation.startswith("[error]"),
        )
        return observation

    def _build_messages(self, task: str, transcript: list[dict[str, str]]) -> list[dict[str, str]]:
        system = self.system_prompt
        if self.memory_context:
            system += "\n\n## Recalled memory\n" + self.memory_context
        messages = [{"role": "system", "content": system}]
        messages.append({"role": "user", "content": f"TASK: {task}"})
        messages.extend(transcript)
        return messages

    def _record(self, transcript: list[dict[str, str]], role: str, content: str) -> None:
        transcript.append({"role": role, "content": content})

    def _after(self, iteration: int, result: IterationResult) -> None:
        if self.on_after_iteration:
            self.on_after_iteration(iteration, result)

    @staticmethod
    def _is_degenerate(recent_texts: list[str], window: int = 3, threshold: float = 0.92) -> bool:
        """True when the last ``window`` responses are near-identical."""
        if len(recent_texts) < window:
            return False
        tail = [_normalize(t) for t in recent_texts[-window:]]
        ratios = [
            difflib.SequenceMatcher(None, tail[i], tail[i + 1]).ratio()
            for i in range(len(tail) - 1)
        ]
        return all(r >= threshold for r in ratios)

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are a capable autonomous agent. Work in small, reversible steps.\n"
            "Respond with EXACTLY ONE JSON object and nothing else:\n"
            '  {"action": {"tool": "<tool name>", "args": {…}}, "thought": "<why>"}\n'
            'or, when the task is complete:\n'
            '  {"reply": "<final answer for the human>"}\n'
            "Prefer the smallest reversible action; verify before claiming success."
        )
