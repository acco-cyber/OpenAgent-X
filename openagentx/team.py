"""X-Team: small-team orchestration — planner, executor, critic, catalog.

Patterns fused from the reference analysis:

* **Delegation catalog** — sub-agent routing is *generated from definition
  metadata*, not hardcoded: add a definition file, the catalog grows
  (agent-zero's insight, kept).
* **Roles over heroes** — one planner (reasoning profile), one executor per
  step (cheapest capable profile), one critic that demands evidence
  (OpenAgent-X verification thesis: failure ≠ false completion).
* **Budgeted subtasks** — every step carries its own ceilings; a step that
  blows its budget fails without poisoning the team run.
* **Everything traced** — subtask dispatch/completion/failure are
  ``EventEnvelopes``, so a team run replays like a single-agent run.

The text protocol stays model-agnostic (same JSON contract as the kernel).
If the planner's output can't be parsed, the team falls back to a single
step covering the whole task — degraded, never stuck.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openagentx.budget import Budget
from openagentx.events import Actor, EventType
from openagentx.llm import LLM
from openagentx.loop import AgentKernel, extract_json_object
from openagentx.trace import TraceLog


# --------------------------------------------------------------- definitions


@dataclass(frozen=True)
class AgentCard:
    """Minimal, contract-aligned view of one agent definition."""

    agent_id: str
    description: str
    supported_task_types: tuple[str, ...] = ()
    runtime_adapter: str = "kernel"

    def matches(self, task_text: str) -> bool:
        hay = task_text.lower()
        return any(t.lower() in hay for t in self.supported_task_types)


_YAML_STRING = re.compile(r'^\s*(agent_id|description|runtime_adapter):\s*["\']?([^"\'\n#]+)', re.MULTILINE)
_YAML_LIST = re.compile(r'^\s*(supported_task_types):\s*\n((?:\s*-\s*[^\n]+\n?)+)', re.MULTILINE)
_YAML_LIST_ITEM = re.compile(r'^\s*-\s*([^\n#]+)', re.MULTILINE)


def catalog_from_dir(defs_dir: str | Path) -> list[AgentCard]:
    """Build the delegation catalog from ``agents/*.yaml`` definitions.

    Parses only the flat subset of YAML those definitions use (scalar fields
    + block lists) — enough for the catalog, without a YAML dependency.
    Invalid files are skipped, never fatal.
    """
    cards: list[AgentCard] = []
    directory = Path(defs_dir)
    if not directory.is_dir():
        return cards
    for path in sorted(directory.glob("*.y*ml")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        scalars = {m.group(1): m.group(2).strip() for m in _YAML_STRING.finditer(text)}
        task_types: tuple[str, ...] = ()
        list_match = _YAML_LIST.search(text)
        if list_match:
            items = _YAML_LIST_ITEM.findall(list_match.group(2))
            task_types = tuple(i.strip().strip("'\"") for i in items if i.strip())
        agent_id = scalars.get("agent_id") or path.stem
        cards.append(
            AgentCard(
                agent_id=agent_id,
                description=scalars.get("description", "")[:160],
                supported_task_types=task_types,
                runtime_adapter=scalars.get("runtime_adapter", "kernel"),
            )
        )
    return cards


def routing_catalog(cards: list[AgentCard], task_text: str) -> str:
    """Render the catalog section the planner sees (auto-generated routing)."""
    matching = [c for c in cards if c.matches(task_text)]
    others = [c for c in cards if not c.matches(task_text)]
    lines = ["## Delegation catalog"]
    if matching:
        lines.append("Specialists matched to this task:")
        for card in matching:
            lines.append(f"- {card.agent_id}: {card.description or '(no description)'}")
    if others:
        lines.append("Other available specialists:")
        for card in others:
            lines.append(f"- {card.agent_id}: {card.description or '(no description)'}")
    return "\n".join(lines)


# -------------------------------------------------------------------- roles


@dataclass
class Step:
    """One planned step with its own budget."""

    index: int
    goal: str
    done_when: str
    capability: str = "general"          # cheap | general | reasoning | code
    max_iterations: int = 6
    status: str = "pending"              # pending | done | failed
    reply: str = ""
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "goal": self.goal, "done_when": self.done_when,
            "capability": self.capability, "status": self.status,
        }


@dataclass
class TeamResult:
    """Terminal outcome of a team run."""

    status: str                                   # done | failed | partial
    reply: str
    steps: list[Step] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "done"


_PLANNER_PROMPT = (
    "You are the planner. Decompose the task into 1–5 small, verifiable steps.\n"
    'Respond with ONE JSON object: {"plan": [{"step": "<goal>", '
    '"done_when": "<verifiable condition>", "capability": "cheap|general|reasoning|code"}]}'
)

_CRITIC_PROMPT = (
    "You are the critic. Judge ONLY from evidence, never from confidence.\n"
    'Respond with ONE JSON object: {"verdict": "pass|fail", "reason": "<why>"}'
)


class Team:
    """Planner → executor(s) → critic, over one shared trace."""

    def __init__(
        self,
        llm: LLM,
        trace: TraceLog,
        *,
        tools: Any | None = None,
        task_id: str | None = None,
        step_budget: Budget | None = None,
    ) -> None:
        self.llm = llm
        self.trace = trace
        self.tools = tools
        self.task_id = task_id
        self.step_budget = step_budget or Budget(max_iterations=6, max_tool_calls=10)

    # ------------------------------------------------------------------ public

    def run(self, task: str, *, catalog_text: str = "") -> TeamResult:
        self.trace.append(
            EventType.TASK_CREATED, task_id=self.task_id,
            actor_type="user", actor_id="human", task=task, mode="team",
        )
        steps = self._plan(task, catalog_text)
        self.trace.append(
            EventType.TASK_PLANNED, task_id=self.task_id, actor_type="agent",
            actor_id="planner", steps=[s.to_dict() for s in steps],
        )

        for step in steps:
            self._execute(task, step)
            self._criticize(step)

        done = [s for s in steps if s.status == "done"]
        if len(done) == len(steps):
            status = "done"
        elif done:
            status = "partial"
        else:
            status = "failed"
        reply = "\n\n".join(
            f"Step {s.index + 1} [{s.status}]: {s.reply or s.evidence or '(no output)'}" for s in steps
        )
        self.trace.append(
            EventType.TASK_COMPLETED if status == "done" else EventType.TASK_FAILED,
            task_id=self.task_id, actor_type="agent", actor_id="team",
            status=status, steps_done=len(done), steps_total=len(steps),
        )
        return TeamResult(status=status, reply=reply, steps=steps)

    # ----------------------------------------------------------------- private

    def _plan(self, task: str, catalog_text: str) -> list[Step]:
        messages = [
            {"role": "system", "content": _PLANNER_PROMPT + ("\n\n" + catalog_text if catalog_text else "")},
            {"role": "user", "content": f"TASK: {task}"},
        ]
        response = self.llm.complete(messages, max_tokens=512)
        parsed = extract_json_object(response.text) or {}
        raw_steps = parsed.get("plan")
        steps: list[Step] = []
        if isinstance(raw_steps, list):
            for i, item in enumerate(raw_steps[:5]):
                if isinstance(item, dict) and item.get("step"):
                    steps.append(
                        Step(
                            index=i,
                            goal=str(item["step"]),
                            done_when=str(item.get("done_when", "step output produced")),
                            capability=str(item.get("capability", "general")),
                        )
                    )
        if not steps:  # degraded mode: never stuck
            steps = [Step(index=0, goal=task, done_when="a direct answer with reasoning")]
        return steps

    def _execute(self, task: str, step: Step) -> None:
        self.trace.append(
            EventType.SUBTASK_DISPATCHED, task_id=self.task_id, actor_type="agent",
            actor_id="team", step=step.index, goal=step.goal, capability=step.capability,
        )
        kernel = AgentKernel(
            self.llm,
            self.trace,
            tools=self.tools,
            budget=self.step_budget,
            task_id=self.task_id,
        )
        step_task = f"{task}\n\nCURRENT STEP {step.index + 1}: {step.goal}\nDone when: {step.done_when}"
        try:
            result = kernel.run(step_task)
        except Exception as exc:  # a step crash must not kill the team
            step.status = "failed"
            step.evidence = f"{type(exc).__name__}: {exc}"
            self.trace.append(
                EventType.SUBTASK_FAILED, task_id=self.task_id, actor_type="runtime",
                actor_id="team", step=step.index, error=step.evidence,
            )
            return
        step.reply = result.reply
        step.evidence = f"kernel status={result.status}, iterations={result.iterations}"
        step.status = "done" if result.ok else "failed"
        event = EventType.SUBTASK_COMPLETED if result.ok else EventType.SUBTASK_FAILED
        self.trace.append(
            event, task_id=self.task_id, actor_type="runtime", actor_id="team",
            step=step.index, status=result.status, usage=result.usage,
        )

    def _criticize(self, step: Step) -> None:
        """Downgrade unverified success: evidence-gated completion."""
        if step.status != "done":
            return
        messages = [
            {"role": "system", "content": _CRITIC_PROMPT},
            {"role": "user", "content": (
                f"STEP GOAL: {step.goal}\nDONE WHEN: {step.done_when}\n"
                f"EXECUTOR REPLY: {step.reply[:1200]}\nEVIDENCE: {step.evidence}"
            )},
        ]
        response = self.llm.complete(messages, max_tokens=256)
        parsed = extract_json_object(response.text) or {}
        verdict = str(parsed.get("verdict", "")).lower()
        if verdict == "fail":
            step.status = "failed"
            step.evidence += f" | critic: {parsed.get('reason', 'unverified')}"
            self.trace.append(
                EventType.VERIFICATION_FAILED, task_id=self.task_id, actor_type="policy",
                actor_id="critic", step=step.index, reason=parsed.get("reason", "unverified"),
            )
        else:
            self.trace.append(
                EventType.VERIFICATION_PASSED, task_id=self.task_id, actor_type="policy",
                actor_id="critic", step=step.index, reason=parsed.get("reason", ""),
            )
