"""Hook policies — pre-tool-call deny rules, observed in the journal.

A :class:`HookPolicy` is an ordered list of deny rules evaluated by the
runner *before* any tool executes. First matching rule wins; everything else
is allowed. Decisions are control-plane facts: the runner journals every
decision as a ``hook`` event, and a denied call never reaches the tool
registry — no ``tool_call``, no ``tool_result``, no side effects. The loop
continues after a denial (the agent observes ``DENY ...`` and can adapt);
a denied attempt still consumed its LLM turn, so it counts as a step.

Example (first matching rule wins; the wildcard denies everything else):

    >>> p = HookPolicy([{"tool": "rm", "reason": "no destructive tools"},
    ...                 {"tool": "*", "reason": "locked down"}])
    >>> p.decide("rm")
    ('deny', 'no destructive tools')
    >>> p.decide("anything")
    ('deny', 'locked down')
    >>> HookPolicy([]).decide("rm")
    ('allow', '')
"""

from __future__ import annotations

ALLOW = "allow"
DENY = "deny"


class HookPolicy:
    """Ordered pre-tool-call deny rules; first match wins."""

    def __init__(self, rules):
        self.rules = []
        for r in rules or []:
            self.rules.append({"tool": str(r.get("tool", "")),
                               "reason": str(r.get("reason", ""))})

    def decide(self, tool: str, args: dict | None = None) -> tuple:
        """Return ``(decision, reason)`` for a tool call attempt."""
        name = str(tool)
        for r in self.rules:
            if r["tool"] == name or r["tool"] == "*":
                return (DENY, r["reason"])
        return (ALLOW, "")

    def rules_snapshot(self) -> list:
        """Copy of the rules (callers cannot mutate policy state)."""
        return [dict(r) for r in self.rules]
