"""X-Tools: one registry, one dispatch choke point, JIT disclosure.

Discipline fused from the reference analysis:

* **One definition source** — every consumer (loop, CLI, prompt compiler,
  future UIs) reads tool metadata from here. Callers may narrow what they
  expose; nobody duplicates definitions.
* **Single choke point** — all execution funnels through
  :meth:`ToolRegistry.dispatch`, which consults the policy engine, runs the
  approval gate, normalizes errors, and truncates oversized output. Tools
  never execute themselves.
* **JIT tool disclosure** — the prompt shows only a core set plus a
  ``find_tools`` meta-tool; the rest is pulled on demand. Huge token savings
  on large toolsets.
* **Diffs-not-dumps** — results report *what changed*, keeping loop context
  flat across iterations.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any, Callable

from openagentx.events import EventType
from openagentx.policy import (
    ASK,
    DENY,
    ActionContext,
    Decision,
    PolicyEngine,
    Tier,
)
from openagentx.trace import TraceLog

Handler = Callable[..., "ToolResult"]
ConfirmFn = Callable[[str, dict[str, Any], str, str], bool]  # (tool, args, tier, reason) -> bool

MAX_OUTPUT_CHARS = 4_000


@dataclass
class ToolResult:
    """Normalized tool outcome. ``diff`` carries what changed, when it did."""

    ok: bool
    output: str
    diff: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tool:
    """A capability: metadata + policy tier + handler, defined in one place."""

    name: str
    description: str
    params: dict[str, Any]                 # JSON-Schema-ish: {"arg": "type|note", …}
    tier: str                              # highest Tier.* the tool needs
    handler: Handler
    core: bool = False                     # core tools are always shown in prompts
    returns_diff: bool = False             # advertise diff-capability to consumers

    def signature(self) -> str:
        args = ", ".join(f'{k}: {v}' for k, v in self.params.items()) or "none"
        return f"{self.name}({args}) -> [{Tier.NAMES.get(self.tier, self.tier)}] {self.description}"


class ToolRegistry:
    """The only place tools are registered, discovered, and executed."""

    def __init__(
        self,
        policy: PolicyEngine | None = None,
        trace: TraceLog | None = None,
        confirm: ConfirmFn | None = None,
        max_output_chars: int = MAX_OUTPUT_CHARS,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self.policy = policy
        self.trace = trace
        self.confirm = confirm
        self.max_output_chars = max_output_chars

    # ---------------------------------------------------------------- registry

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    # ------------------------------------------------------------ JIT disclosure

    def visible_tools(self) -> list[Tool]:
        """Tools the model may see under the current policy (denied vanish)."""
        if self.policy is None:
            return list(self._tools.values())
        visible = []
        for tool in self._tools.values():
            if self.policy.prune_description(tool.name, tool.description, tool.tier) is not None:
                visible.append(tool)
        return visible

    def core_tools(self) -> list[Tool]:
        """Core set for prompts; non-core reachable via ``find_tools``."""
        visible = self.visible_tools()
        core = [t for t in visible if t.core]
        return core[:8]  # prompt budget discipline

    def find_tools(self, query: str, limit: int = 5) -> list[Tool]:
        """Keyword-overlap search over tool metadata (the JIT pattern)."""
        terms = [t for t in query.lower().replace(",", " ").split() if t]
        scored: list[tuple[float, Tool]] = []
        for tool in self.visible_tools():
            hay = f"{tool.name} {tool.description} {' '.join(tool.params)}".lower()
            score = sum(1.0 for term in terms if term in hay)
            if fnmatch.fnmatchcase(tool.name, f"*{query.lower()}*"):
                score += 2.0
            if score > 0:
                scored.append((score, tool))
        scored.sort(key=lambda pair: -pair[0])
        return [tool for _score, tool in scored[:limit]]

    # -------------------------------------------------------------- choke point

    def dispatch(self, name: str, args: dict[str, Any], task_id: str | None = None) -> str:
        """Execute one tool call — the single path every caller must use.

        Order: lookup → policy verdict → (ask) human approval → execute →
        normalize/truncate. Denied and failed calls never raise; they return
        ``[denied …]`` / ``[error …]`` strings so the loop can observe them.
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"[error] unknown tool {name!r}; use find_tools to list capabilities"

        decision = self._decide(tool, args, task_id)
        if decision.verdict == DENY:
            return f"[denied] {name}: {decision.reason} (rule={decision.rule_id})"
        if decision.verdict == ASK:
            if self.confirm is None or not self.confirm(name, args, tool.tier, decision.reason):
                return f"[denied] {name}: human approval was not granted (rule={decision.rule_id})"

        try:
            result = tool.handler(**args)
        except TypeError as exc:
            return f"[error] bad arguments for {name}: {exc}"
        except Exception as exc:  # tool crash → observation, not loop crash
            return f"[error] {name} failed: {type(exc).__name__}: {exc}"

        return self._render(result)

    # ----------------------------------------------------------------- private

    def _decide(self, tool: Tool, args: dict[str, Any], task_id: str | None) -> Decision:
        ctx = ActionContext(tool=tool.name, tier=tool.tier, args=args, task_id=task_id)
        if self.policy is None:
            return Decision(verdict="allow", rule_id="no-policy", reason="no policy attached")
        decision = self.policy.evaluate(ctx)
        if self.trace is not None:
            self.trace.append(
                EventType.POLICY_DECISION,
                task_id=task_id,
                actor_type="policy",
                actor_id="engine",
                tool=tool.name,
                tier=tool.tier,
                verdict=decision.verdict,
                rule_id=decision.rule_id,
                reason=decision.reason,
            )
        return decision

    def _render(self, result: ToolResult) -> str:
        text = result.output if result.ok else f"[error] {result.output}"
        if result.diff:
            text = f"{text}\n--- diff ---\n{result.diff}"
        if len(text) > self.max_output_chars:
            cut = self.max_output_chars
            text = text[:cut] + f"\n… [truncated {len(text) - cut} chars — diffs-not-dumps]"
        return text

    # ------------------------------------------------------------ prompt surface

    def prompt_section(self) -> str:
        """Render the tools section for the system prompt (JIT style)."""
        core = self.core_tools()
        lines = ["## Tools", ""]
        for tool in core:
            lines.append(f"- {tool.signature()}")
        others = [t for t in self.visible_tools() if t not in core]
        if others:
            lines.append("")
            lines.append(
                f"{len(others)} more tools are available on demand: call "
                '`{"action": {"tool": "find_tools", "args": {"query": "…"}}}` '
                "to discover them by keyword before using them."
            )
        return "\n".join(lines)
