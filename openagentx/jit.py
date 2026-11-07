"""Just-in-time tool disclosure: the model only sees what the policy revealed.

A visibility layer between the registry and the loop. Tools stay registered
and fully executable, but the model is only *told* about the tools the
disclosure policy has revealed so far:

1. **Always-on core** — a small set of tools (plus the ``tools_expand``
   control-plane escape hatch) is visible from turn zero.
2. **Keyword rules** — deterministic rules disclose tool groups when any
   keyword appears in the task text or in an observation; matching is
   case-insensitive, sets are kept sorted, and re-runs are identical.
3. **On-demand expansion** — the model calls ``tools_expand`` with a tool
   name to request its full schema; the request lands as an ordinary
   journaled tool call, and the target tool becomes visible immediately.
4. **Loud refusals** — calling an undisclosed tool is refused before the
   hook layer and before any execution: exactly one ``tool_hidden`` event,
   an observation telling the model how to request disclosure, and zero
   side effects. Visibility precedes execution policy — a hidden tool
   never reaches hooks, budgets of tool results, or the registry.
5. **Journaled visibility** — every visibility change (turn-zero set,
   keyword-driven growth, expansion-driven growth) is journaled as a
   ``tool_disclose`` event naming the full visible set and what was added.

Failure contracts (all raise, never silent): ``always`` tools and rule
tools must exist in the registry, unknown ``tools_expand`` targets name
themselves, and ``max_visible`` caps rule-driven additions deterministically
(sorted order) without ever hiding the control plane.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tools import Tool, ToolError, ToolRegistry

CONTROL_TOOL = "tools_expand"


@dataclass(frozen=True)
class DisclosureRule:
    """Disclose *tools* when any lowercase *keyword* appears in the surface text."""

    keywords: tuple
    tools: tuple


class JITDisclosure:
    """Deterministic visibility policy over a real ``ToolRegistry``."""

    def __init__(self, registry: ToolRegistry, rules=(), always=("think",),
                 max_visible: int = 0):
        self.registry = registry
        self.always = tuple(sorted({str(t) for t in always} | {CONTROL_TOOL}))
        missing = [t for t in self.always if t != CONTROL_TOOL
                   and registry.get(t) is None]
        if missing:
            raise ValueError(
                f"always-disclosed tools missing from registry: {', '.join(missing)}")
        self.rules = []
        for rule in rules:
            rule_tools = tuple(str(t) for t in rule.tools)
            unknown = [t for t in rule_tools if registry.get(t) is None]
            if unknown:
                raise ValueError(
                    f"disclosure rule names unknown tools: {', '.join(unknown)}")
            self.rules.append(DisclosureRule(
                tuple(str(k).lower() for k in rule.keywords), rule_tools))
        if int(max_visible) < 0:
            raise ValueError("max_visible must be >= 0 (0 = unlimited)")
        self.max_visible = int(max_visible)
        self.visible: set = set(self.always)

    def update(self, surface: str) -> list:
        """Apply keyword rules to *surface*; return sorted newly-visible names.

        Rule hits are capped at ``max_visible`` (sorted order, deterministic)
        before joining the visible set; the always-on core and the control
        plane are exempt from the cap.
        """
        low = str(surface).lower()
        hits: set = set()
        for rule in self.rules:
            if any(k in low for k in rule.keywords):
                hits.update(rule.tools)
        if self.max_visible:
            hits = set(sorted(hits)[: self.max_visible])
        added = sorted(hits - self.visible)
        self.visible |= hits
        return added

    def check(self, tool: str) -> bool:
        """True when *tool* is currently visible to the model."""
        return tool in self.visible

    def visible_names(self) -> list:
        return sorted(self.visible)

    def visible_schemas(self) -> list:
        """What the model may see: full descriptors, sorted by name."""
        out = []
        for name in self.visible_names():
            t = self.registry.get(name)
            if t is not None:
                out.append({"name": t.name, "description": t.description,
                            "schema": t.schema})
        return out

    def expand(self, name: str) -> dict:
        """On-demand disclosure: make *name* visible, return its full descriptor."""
        t = self.registry.get(str(name))
        if t is None:
            known = ", ".join(sorted(t2.name for t2 in
                                     (self.registry.get(n) for n in self.registry.names())
                                     if t2 is not None))
            raise ToolError(f"unknown tool '{name}' (known: {known})")
        self.visible.add(t.name)
        return {"tool": t.name, "name": t.name, "description": t.description,
                "schema": t.schema}

    def expand_tool(self) -> Tool:
        """The control-plane tool the model calls to request disclosure."""
        return Tool(
            CONTROL_TOOL,
            "request full schema disclosure for one tool by name",
            {"properties": {"tool": {"type": "string"}}, "required": ["tool"]},
            lambda tool: self.expand(str(tool)),
        )


class JITAgentRunner:
    """``AgentRunner`` wired to a disclosure policy.

    Refuses undisclosed calls before execution, journals every visibility
    change, and registers the ``tools_expand`` control-plane tool into the
    registry so the model can request disclosure mid-run.
    """

    def __init__(self, llm, tools: ToolRegistry, journal_path, disclosure: JITDisclosure,
                 **kwargs):
        from .runner import AgentRunner

        if tools.get(CONTROL_TOOL) is None:
            tools.register(disclosure.expand_tool())
        self.disclosure = disclosure
        self._runner = AgentRunner(llm, tools, journal_path,
                                   disclosure=disclosure, **kwargs)

    def run(self, task: str):
        return self._runner.run(task)
