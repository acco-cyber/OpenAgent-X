"""X-Guard: the pure policy seam — evaluate(context) → Allow | Ask | Deny.

Lessons fused here (concept-level, from the reference analysis):

* **Policy outside prompts** (ADR-007): the prompt never grants power; the
  engine does. If a tool is denied, the model is *also* not told it exists
  (capability-text pruning) — see :meth:`PolicyEngine.prune_description`.
* **Tri-state verdicts** (allow / ask / deny) with stable ``rule_id``s so
  audit trails group by rule, not by string accident.
* **Denial parity**: the verdict binds to the *target* (tool + tier), not to
  the caller or transport. A fallback path cannot bypass what the main path
  was denied.
* The engine is a **pure function** of its rules + the action context: no
  I/O, no clock, no RNG — deterministic and trivially auditable.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any


class Tier:
    """Permission tiers, aligned with the manifest's P0–P4 scale."""

    P0 = "P0"  # read-only: inspect, search, summarize
    P1 = "P1"  # reversible local: draft, edit files inside the workspace
    P2 = "P2"  # execute: run code / shell inside a sandbox
    P3 = "P3"  # network: reach external services
    P4 = "P4"  # privileged: host-level, irreversible, or destructive

    ALL = (P0, P1, P2, P3, P4)
    NAMES = {
        P0: "read-only",
        P1: "reversible-local",
        P2: "execute",
        P3: "network",
        P4: "privileged",
    }


ALLOW = "allow"
ASK = "ask"
DENY = "deny"


@dataclass(frozen=True)
class ActionContext:
    """Everything the policy may look at when deciding. Nothing else."""

    tool: str
    tier: str                      # one of Tier.* (highest tier the tool needs)
    args: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    actor: str = "kernel"


@dataclass(frozen=True)
class Decision:
    """One policy verdict. ``rule_id`` is stable for audit grouping."""

    verdict: str                   # ALLOW | ASK | DENY
    rule_id: str
    reason: str


@dataclass(frozen=True)
class PolicyRule:
    """A tri-state rule. First matching rule (by priority, then order) wins.

    ``tools`` and ``tiers`` use glob patterns (``fnmatch``): ``"fs_*"``,
    ``"web_*"``, tier ``"P[01]"`` … Empty list = matches everything.
    """

    rule_id: str
    verdict: str                   # ALLOW | ASK | DENY
    tools: tuple[str, ...] = ()
    tiers: tuple[str, ...] = ()
    reason: str = ""
    priority: int = 100            # lower = evaluated first

    def matches(self, ctx: ActionContext) -> bool:
        tool_hit = not self.tools or any(
            fnmatch.fnmatchcase(ctx.tool, pat) for pat in self.tools
        )
        tier_hit = not self.tiers or any(
            fnmatch.fnmatchcase(ctx.tier, pat) for pat in self.tiers
        )
        return tool_hit and tier_hit


class PolicyEngine:
    """Deterministic tri-state policy engine (the only authority on power).

    Rules are evaluated in ``(priority, declaration order)``; the first match
    returns its verdict. If nothing matches, ``default_verdict`` applies
    (deny-closed by default — a security product that starts open stays open).
    """

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        default_verdict: str = DENY,
        default_reason: str = "no policy matched (deny-closed default)",
    ) -> None:
        self.rules = sorted(rules or [], key=lambda r: r.priority)
        self.default_verdict = default_verdict
        self.default_reason = default_reason

    def evaluate(self, ctx: ActionContext) -> Decision:
        """The pure seam: context in, verdict out. No side effects."""
        for rule in self.rules:
            if rule.matches(ctx):
                return Decision(
                    verdict=rule.verdict,
                    rule_id=rule.rule_id,
                    reason=rule.reason or f"matched rule {rule.rule_id}",
                )
        return Decision(
            verdict=self.default_verdict, rule_id="default", reason=self.default_reason
        )

    # ------------------------------------------------- capability text control

    def prune_description(self, tool_name: str, description: str, tier: str) -> str | None:
        """Return the tool description the model may *see*, or ``None``.

        Denied tools vanish from the prompt entirely (the model can't
        hallucinate a capability it was never told about); ask-gated tools
        are shown with an explicit approval notice.
        """
        decision = self.evaluate(ActionContext(tool=tool_name, tier=tier))
        if decision.verdict == DENY:
            return None
        if decision.verdict == ASK:
            return f"{description} (requires human approval per run)"
        return description

    def allowed_tools(self, tools: list[tuple[str, str]]) -> list[str]:
        """Names of tools the policy lets the model see, given (name, tier)."""
        return [
            name for name, tier in tools
            if self.evaluate(ActionContext(tool=name, tier=tier)).verdict != DENY
        ]


def default_policy(*, allow_workspace: bool = True) -> PolicyEngine:
    """A sane starter policy.

    Reads always allowed; workspace writes allowed; execution and network
    ask-first; privileged denied outright.
    """
    rules = [
        PolicyRule(
            rule_id="reads-allowed", verdict=ALLOW, tools=("*",), tiers=("P0",),
            reason="read-only actions are always allowed", priority=10,
        ),
        PolicyRule(
            rule_id="dangerous-denied", verdict=DENY, tools=("*",), tiers=("P4",),
            reason="privileged/irreversible actions are denied in default policy",
            priority=5,
        ),
    ]
    if allow_workspace:
        rules.append(
            PolicyRule(
                rule_id="workspace-writes", verdict=ALLOW, tools=("fs_*", "think", "find_tools"),
                tiers=("P1", "P2"), reason="reversible local edits are allowed", priority=20,
            )
        )
    rules += [
        PolicyRule(
            rule_id="execute-ask", verdict=ASK, tools=("*",), tiers=("P2",),
            reason="code execution requires human approval", priority=30,
        ),
        PolicyRule(
            rule_id="network-ask", verdict=ASK, tools=("*",), tiers=("P3",),
            reason="network egress requires human approval", priority=40,
        ),
    ]
    return PolicyEngine(rules=rules)
