"""Agent workforce contracts — the blueprint's specialists, as code.

Ported from the HYDRION ONE blueprint (``docs/blueprint/``), sections 7, 11
and 6, as one small deterministic contract layer:

- **§7 agent workforce** — every agent is a *specialist execution profile*
  with an explicit contract, never an independent sovereign assistant.  The
  eight canonical profiles (research, coding, data, math, browser, writing,
  memory, qa) are frozen constants; each runs under the same task ID,
  permission service, budget ledger and audit rules.
- **§11 permission tiers** — P0..P4, enforced at invocation time, *outside*
  model prompts.  "Denied actions do not become allowed through prompting":
  :func:`check_permission` has deliberately no prompt/override parameter —
  the function signature is the security boundary.
- **§6 capability-aware routing** — hard capability and data-policy filters
  run *before* scoring; only eligible candidates are scored; the fallback
  must also pass the hard filters ("do not silently switch to a model that
  lacks a required capability"); and the decision records *why* every
  candidate was accepted or rejected.
- **§5 reliability** — budgets are hard: :class:`BudgetLedger` fails closed,
  task budgets are capped by the agent's contract, and a ``completed``
  result without evidence refs is a contract violation ("evidence before
  claims").

Everything here is pure stdlib, deterministic and offline — no wall-clock,
no network, no I/O.  The tier table and the eight profiles are the two
tables the whole module is honest about: drift them and the drill fails.

Example (the roster and one least-privilege refusal):

    >>> from openagentx.workforce import PROFILES, profiles, check_permission
    >>> tuple(p.agent_id for p in profiles())
    ('browser', 'coding', 'data', 'math', 'memory', 'qa', 'research', 'writing')
    >>> d = check_permission(PROFILES["research"], "shell")
    >>> d.allowed
    False
    >>> d.reason
    "tool 'shell' is outside research's allowlist"

Two gates, allowlist first, then ceiling:

    >>> from openagentx.workforce import AgentDefinition, ContractError
    >>> escalator = AgentDefinition(
    ...     agent_id="escalator", version="1.0.0",
    ...     supported_task_types=("ops",),
    ...     required_capabilities=("code",),
    ...     allowed_tools=("read_file", "shell"),
    ...     permission_ceiling="P1",
    ...     max_tool_calls=5, max_tokens=4000,
    ...     verification_policy=("tests",),
    ...     runtime_adapter="builtin")
    >>> d2 = check_permission(escalator, "shell")
    >>> d2.reason
    "tool 'shell' requires tier P2 but escalator's ceiling is P1"

A contract that would let the agent grant itself a higher ceiling is
refused at construction:

    >>> AgentDefinition(
    ...     agent_id="sneak", version="1.0.0",
    ...     supported_task_types=("ops",),
    ...     required_capabilities=("code",),
    ...     allowed_tools=("read_file",),
    ...     permission_ceiling="P9",
    ...     max_tool_calls=5, max_tokens=4000,
    ...     verification_policy=("tests",),
    ...     runtime_adapter="builtin")
    Traceback (most recent call last):
        ...
    openagentx.workforce.ContractError: permission_ceiling must be one of P0, P1, P2, P3, P4
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
AGENT_ID = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


class WorkforceError(ValueError):
    """Base class for every workforce contract violation."""


class ContractError(WorkforceError):
    """A definition, task or result violates its contract."""


class PermissionDenied(WorkforceError):
    """Raised by :func:`require` when a two-gate check refuses."""


class BudgetExhausted(WorkforceError):
    """A hard tool-call budget ran out — fail closed, never soft-degrade."""


class HandoffError(WorkforceError):
    """A structured handoff or verifier pairing violates §7."""


# ---------------------------------------------------------------------------
# §11 permission tiers — the least-privilege vocabulary
# ---------------------------------------------------------------------------

TIERS: dict[str, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}

# A tool's tier is the least-privileged level that may invoke it
# (blueprint §11 table: read-only → reversible local → sandboxed →
# external side effect → privileged).
TOOL_TIERS: dict[str, str] = {
    "search": "P0", "fetch": "P0", "read_file": "P0",
    "write_draft": "P1", "edit_memory": "P1",
    "shell": "P2", "test_runner": "P2", "python_exec": "P2",
    "browser_nav": "P2",
    "send_email": "P3", "create_pr": "P3",
    "prod_deploy": "P4", "financial_op": "P4",
}


# ---------------------------------------------------------------------------
# §7 the agent contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentDefinition:
    """The versioned contract every specialist runs under (§7).

    ``permission_ceiling`` is the *highest* tier the agent can ever reach;
    ``allowed_tools`` is the whole universe of tools it may even ask about.
    Both gates are checked at invocation time, not in prompts.
    """

    agent_id: str
    version: str
    supported_task_types: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    permission_ceiling: str
    max_tool_calls: int
    max_tokens: int
    verification_policy: tuple[str, ...]
    runtime_adapter: str

    def __post_init__(self) -> None:
        if not AGENT_ID.match(self.agent_id):
            raise ContractError(
                f"agent_id must match {AGENT_ID.pattern} (got {self.agent_id!r})")
        if not SEMVER.match(self.version):
            raise ContractError(
                f"version must be semver major.minor.patch (got {self.version!r})")
        for name, value in (("supported_task_types", self.supported_task_types),
                            ("required_capabilities", self.required_capabilities),
                            ("allowed_tools", self.allowed_tools),
                            ("verification_policy", self.verification_policy)):
            if not value:
                raise ContractError(f"{name} must be non-empty")
            object.__setattr__(self, name, tuple(value))
        if self.permission_ceiling not in TIERS:
            raise ContractError(
                "permission_ceiling must be one of "
                + ", ".join(TIERS))
        if not isinstance(self.max_tool_calls, int) or self.max_tool_calls < 1:
            raise ContractError("max_tool_calls must be a positive integer")
        if not isinstance(self.max_tokens, int) or self.max_tokens < 1:
            raise ContractError("max_tokens must be a positive integer")
        unknown = [t for t in self.allowed_tools if t not in TOOL_TIERS]
        if unknown:
            raise ContractError(
                f"tool {unknown[0]!r} is not in the tier table — "
                "the table is the whole universe of invocable tools")


def _profile(agent_id: str, version: str, task_types: tuple[str, ...],
             capabilities: tuple[str, ...], tools: tuple[str, ...],
             ceiling: str, tool_calls: int, tokens: int,
             policy: tuple[str, ...], adapter: str = "builtin") -> AgentDefinition:
    return AgentDefinition(
        agent_id=agent_id, version=version,
        supported_task_types=task_types, required_capabilities=capabilities,
        allowed_tools=tools, permission_ceiling=ceiling,
        max_tool_calls=tool_calls, max_tokens=tokens,
        verification_policy=policy, runtime_adapter=adapter)


# The §7 roster.  Authored least-privilege: research is read-only (P0);
# writing and memory touch only reversible local state (P1); the six
# sandbox-compute specialists stop at P2.  No profile ships with a P3/P4
# tool in its allowlist — external side effects and privileged operations
# are simply outside the workforce's reach.
PROFILES: dict[str, AgentDefinition] = {
    "research": _profile(
        "research", "1.0.0", ("research", "summarize"),
        ("web_search", "source_citation"),
        ("search", "fetch", "read_file"), "P0", 25, 12000,
        ("citation_check",)),
    "coding": _profile(
        "coding", "1.0.0", ("coding",),
        ("code", "tool_calling"),
        ("read_file", "write_draft", "shell", "test_runner"), "P2", 40, 20000,
        ("diff_review", "tests")),
    "data": _profile(
        "data", "1.0.0", ("analysis",),
        ("code", "structured_output"),
        ("read_file", "python_exec", "test_runner"), "P2", 30, 20000,
        ("schema_checks",)),
    "math": _profile(
        "math", "1.0.0", ("derivation", "verification"),
        ("reasoning", "code"),
        ("read_file", "python_exec"), "P2", 20, 16000,
        ("derivation_check",)),
    "browser": _profile(
        "browser", "1.0.0", ("browsing",),
        ("tool_calling",),
        ("fetch", "browser_nav"), "P2", 30, 12000,
        ("screenshot_confirmation",)),
    "writing": _profile(
        "writing", "1.0.0", ("writing",),
        ("structured_output",),
        ("read_file", "write_draft"), "P1", 15, 16000,
        ("evidence_consistency",)),
    "memory": _profile(
        "memory", "1.0.0", ("curation",),
        ("structured_output",),
        ("read_file", "edit_memory"), "P1", 15, 8000,
        ("provenance",)),
    "qa": _profile(
        "qa", "1.0.0", ("verification",),
        ("tool_calling", "code"),
        ("read_file", "search", "test_runner"), "P2", 25, 12000,
        ("independent_evidence",)),
}


def profiles() -> tuple[AgentDefinition, ...]:
    """The eight canonical profiles, deterministically ordered by id."""
    return tuple(PROFILES[k] for k in sorted(PROFILES))


@dataclass(frozen=True)
class Decision:
    """The outcome of a two-gate permission check — an auditable record."""

    allowed: bool
    reason: str
    tool: str
    agent_id: str


def check_permission(agent: AgentDefinition, tool: str) -> Decision:
    """Two fail-closed gates at invocation time — allowlist, then ceiling.

    There is deliberately no prompt/override/ask-forgiveness parameter
    (§11: "permission enforcement outside model prompts"; "denied actions
    do not become allowed through prompting").  The signature is the
    boundary: an agent literally has no way to beg its way through.
    """
    if tool not in TOOL_TIERS:
        return Decision(
            False,
            f"unknown tool {tool!r} — the tier table is the whole universe "
            "of invocable tools",
            tool, agent.agent_id)
    if tool not in agent.allowed_tools:
        return Decision(
            False,
            f"tool {tool!r} is outside {agent.agent_id}'s allowlist",
            tool, agent.agent_id)
    if TIERS[TOOL_TIERS[tool]] > TIERS[agent.permission_ceiling]:
        return Decision(
            False,
            f"tool {tool!r} requires tier {TOOL_TIERS[tool]} but "
            f"{agent.agent_id}'s ceiling is {agent.permission_ceiling}",
            tool, agent.agent_id)
    return Decision(
        True,
        f"{tool!r} within allowlist and ceiling {agent.permission_ceiling}",
        tool, agent.agent_id)


def require(agent: AgentDefinition, tool: str) -> Decision:
    """:func:`check_permission` that raises :class:`PermissionDenied`."""
    d = check_permission(agent, tool)
    if not d.allowed:
        raise PermissionDenied(d.reason)
    return d


# ---------------------------------------------------------------------------
# §5 reliability — hard budgets and evidence-gated results
# ---------------------------------------------------------------------------


class BudgetLedger:
    """A hard tool-call budget that fails closed (§5: "hard tool budgets")."""

    def __init__(self, agent_id: str, max_tool_calls: int) -> None:
        if not isinstance(max_tool_calls, int) or max_tool_calls < 1:
            raise ContractError("max_tool_calls must be a positive integer")
        self.agent_id = agent_id
        self.max_tool_calls = max_tool_calls
        self._spent = 0

    @property
    def spent(self) -> int:
        return self._spent

    @property
    def remaining(self) -> int:
        return self.max_tool_calls - self._spent

    def spend(self, n: int = 1) -> int:
        """Spend ``n`` calls; return the remaining budget.

        >>> led = BudgetLedger("research", 2)
        >>> led.spend()
        1
        >>> led.spend()
        0
        >>> led.spend()
        Traceback (most recent call last):
            ...
        openagentx.workforce.BudgetExhausted: research exhausted its tool-call budget: 2 of 2 spent
        """
        if n < 1:
            raise ContractError("spend requires n >= 1")
        if self._spent + n > self.max_tool_calls:
            raise BudgetExhausted(
                f"{self.agent_id} exhausted its tool-call budget: "
                f"{self.max_tool_calls} of {self.max_tool_calls} spent")
        self._spent += n
        return self.remaining


def validate_task(task: dict, agent: AgentDefinition) -> dict:
    """Validate a dispatch request against the agent's contract, fail-closed.

    The task's budget is *capped* by the definition — a task may ask for
    less, never for more (§5: budgets are set by the orchestrator, not the
    model).  Returns the task unchanged; raises :class:`ContractError`.

    >>> from openagentx.workforce import PROFILES, validate_task
    >>> t = {"task_id": "t-1", "objective": "sourced survey",
    ...      "agent_id": "research",
    ...      "budget": {"max_tool_calls": 5, "max_tokens": 1000},
    ...      "acceptance_criteria": ["at least 8 primary sources"],
    ...      "permission_scope": ["search", "fetch"]}
    >>> validate_task(t, PROFILES["research"]) == t
    True
    >>> validate_task(dict(t, budget={"max_tool_calls": 500, "max_tokens": 1000}),
    ...               PROFILES["research"])
    Traceback (most recent call last):
        ...
    openagentx.workforce.ContractError: task budget max_tool_calls=500 exceeds research's contract cap of 25
    """
    if task.get("agent_id") != agent.agent_id:
        raise ContractError(
            f"task is addressed to {task.get('agent_id')!r} but validated "
            f"against {agent.agent_id!r}")
    for key in ("task_id", "objective", "budget", "acceptance_criteria",
                "permission_scope"):
        if key not in task:
            raise ContractError(f"task is missing required key {key!r}")
    budget = task["budget"]
    for cap, limit in (("max_tool_calls", agent.max_tool_calls),
                       ("max_tokens", agent.max_tokens)):
        asked = budget.get(cap)
        if not isinstance(asked, int) or asked < 1:
            raise ContractError(f"task budget {cap} must be a positive integer")
        if asked > limit:
            raise ContractError(
                f"task budget {cap}={asked} exceeds {agent.agent_id}'s "
                f"contract cap of {limit}")
    criteria = task["acceptance_criteria"]
    if (not isinstance(criteria, list) or not criteria
            or not all(isinstance(c, str) and c.strip() for c in criteria)):
        raise ContractError(
            "acceptance_criteria must be a non-empty list of non-empty "
            "strings — a dispatch without criteria cannot be verified")
    scope = task["permission_scope"]
    if (not isinstance(scope, list) or not scope
            or not set(scope).issubset(agent.allowed_tools)):
        raise ContractError(
            "permission_scope must be a non-empty subset of the agent's "
            "allowlist")
    return task


def validate_result(result: dict, agent: AgentDefinition) -> dict:
    """Validate an execution report ("evidence before claims", §1 principle).

    >>> from openagentx.workforce import PROFILES, validate_result
    >>> r = {"task_id": "t-1", "agent_id": "research", "status": "completed",
    ...      "summary": "8 primary sources, 2 discarded as stale",
    ...      "evidence_refs": ["source:1", "source:2"]}
    >>> validate_result(r, PROFILES["research"]) == r
    True
    >>> validate_result(dict(r, evidence_refs=[]), PROFILES["research"])
    Traceback (most recent call last):
        ...
    openagentx.workforce.ContractError: a 'completed' result must carry evidence refs (evidence before claims)
    """
    if result.get("agent_id") != agent.agent_id:
        raise ContractError(
            f"result claims agent {result.get('agent_id')!r} but validated "
            f"against {agent.agent_id!r}")
    for key in ("task_id", "status", "summary", "evidence_refs"):
        if key not in result:
            raise ContractError(f"result is missing required key {key!r}")
    status = result["status"]
    if status not in ("completed", "failed", "cancelled"):
        raise ContractError(
            f"status must be completed|failed|cancelled (got {status!r})")
    if not isinstance(result["summary"], str) or not result["summary"].strip():
        raise ContractError("summary must be a non-empty string")
    refs = result["evidence_refs"]
    if not isinstance(refs, list):
        raise ContractError("evidence_refs must be a list")
    if status == "completed" and not refs:
        raise ContractError(
            "a 'completed' result must carry evidence refs "
            "(evidence before claims)")
    return result


# ---------------------------------------------------------------------------
# §6 capability-aware routing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelCandidate:
    """One model deployment in the registry (§6 registry schema, condensed).

    ``quality`` is a *measured* score, never a marketing label; ``cost``
    is USD per 1k tokens; ``data_policy`` is ``standard`` or ``restricted``
    (a restricted deployment is the only one allowed to see private data).
    """

    model_id: str
    capabilities: frozenset[str]
    quality: float
    availability: float
    cost: float
    data_policy: str = "standard"

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ContractError("model_id must be non-empty")
        if self.data_policy not in ("standard", "restricted"):
            raise ContractError(
                "data_policy must be 'standard' or 'restricted'")
        for name in ("quality", "availability"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ContractError(f"{name} must be within [0, 1]")
        if self.cost < 0.0:
            raise ContractError("cost must be non-negative")


@dataclass(frozen=True)
class RoutingDecision:
    """The persisted record of one routing decision (§6 step 4-5)."""

    requirements: tuple[str, ...]
    data_class: str
    chosen: str
    fallback: str
    reasons: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)
    scores: tuple[tuple[str, float], ...] = field(default_factory=tuple)


def route(requirements, data_class: str,
          candidates) -> RoutingDecision:
    """The §6 pipeline: hard filters → score the eligible → choose + fallback.

    - Hard capability filter: a candidate missing any requirement is
      rejected *with a named reason* — never silently demoted to fallback.
    - Data-policy filter: private data may only go to restricted-policy
      deployments.
    - Score (eligible only): ``2.0`` capability fit (guaranteed 1.0 after
      the hard filter, so the router can never trade a required capability
      for a cheaper token) ``+ 2.0 * quality + 0.5 * availability −
      cost / (cost + 1)``.  Deterministic tie-break on model_id.
    - Fallback: the next *eligible* candidate, or none — a fallback that
      fails the hard constraints is not a fallback.
    """
    reqs = tuple(sorted(set(requirements)))
    if not reqs:
        raise ContractError("routing without requirements is not a decision")
    if data_class not in ("standard", "private"):
        raise ContractError("data_class must be 'standard' or 'private'")
    reasons: list[tuple[str, str, str]] = []
    eligible: list[tuple[ModelCandidate, float]] = []
    for c in candidates:
        missing = [r for r in reqs if r not in c.capabilities]
        if missing:
            reasons.append((c.model_id, "rejected",
                            f"missing hard capability: {missing[0]}"))
        elif data_class == "private" and c.data_policy != "restricted":
            reasons.append((c.model_id, "rejected",
                            "data class 'private' requires a "
                            "restricted-policy deployment"))
        else:
            score = round(
                2.0 + 2.0 * c.quality + 0.5 * c.availability
                - c.cost / (c.cost + 1.0), 3)
            eligible.append((c, score))
            reasons.append((c.model_id, "accepted",
                            f"eligible; score {score}"))
    eligible.sort(key=lambda p: (-p[1], p[0].model_id))
    chosen = eligible[0][0].model_id if eligible else ""
    fallback = eligible[1][0].model_id if len(eligible) > 1 else ""
    return RoutingDecision(
        requirements=reqs, data_class=data_class, chosen=chosen,
        fallback=fallback, reasons=tuple(reasons),
        scores=tuple((m, s) for m, s in
                     ((c.model_id, s) for c, s in eligible)))


# ---------------------------------------------------------------------------
# §7 collaboration rules — structured handoffs, independent verification
# ---------------------------------------------------------------------------


def validate_handoff(handoff: dict, producer: AgentDefinition,
                     consumer: AgentDefinition) -> dict:
    """Validate a structured handoff (§7: "limit agent-to-agent chat").

    Every handoff states its objective, acceptance criteria and the
    artifact references being passed — a handoff without acceptance
    criteria cannot be verified downstream and is refused.

    >>> from openagentx.workforce import PROFILES, validate_handoff
    >>> h = {"from_agent": "research", "to_agent": "writing",
    ...      "objective": "turn 8 sources into a sourced report",
    ...      "acceptance_criteria": ["every claim carries a citation"],
    ...      "artifact_refs": ["artifact:report-draft"]}
    >>> validate_handoff(h, PROFILES["research"], PROFILES["writing"]) == h
    True
    """
    if handoff.get("from_agent") != producer.agent_id:
        raise ContractError(
            f"handoff from_agent {handoff.get('from_agent')!r} does not "
            f"match producer {producer.agent_id!r}")
    if handoff.get("to_agent") != consumer.agent_id:
        raise ContractError(
            f"handoff to_agent {handoff.get('to_agent')!r} does not match "
            f"consumer {consumer.agent_id!r}")
    for key in ("objective", "acceptance_criteria", "artifact_refs"):
        if key not in handoff:
            raise ContractError(f"handoff is missing required key {key!r}")
    criteria = handoff["acceptance_criteria"]
    if (not isinstance(criteria, list) or not criteria
            or not all(isinstance(c, str) and c.strip() for c in criteria)):
        raise ContractError(
            "handoff acceptance_criteria must be a non-empty list — a "
            "handoff that cannot be verified is a chat, not a handoff")
    if not isinstance(handoff["artifact_refs"], list):
        raise ContractError("artifact_refs must be a list")
    return handoff


def require_independent_verifier(producer_id: str, verifier_id: str) -> None:
    """§7: "the verifier should be selected independently of the producer."

    >>> from openagentx.workforce import require_independent_verifier
    >>> require_independent_verifier("writing", "qa") is None
    True
    >>> require_independent_verifier("writing", "writing")
    Traceback (most recent call last):
        ...
    openagentx.workforce.HandoffError: the verifier must be selected independently of the producer: writing cannot verify writing
    """
    if producer_id == verifier_id:
        raise HandoffError(
            f"the verifier must be selected independently of the producer: "
            f"{producer_id} cannot verify {verifier_id}")


# ---------------------------------------------------------------------------
# §12 event naming — the workforce's observable vocabulary
# ---------------------------------------------------------------------------

WORKFORCE_EVENTS = frozenset({
    "agent.started", "agent.model_selected", "agent.tool_call.started",
    "agent.tool_call.completed", "agent.budget_exhausted",
    "agent.permission_denied", "agent.completed", "handoff.accepted",
})


def check_event_name(name: str) -> str:
    """Return ``name`` if it is in the canonical workforce vocabulary.

    >>> from openagentx.workforce import check_event_name
    >>> check_event_name("agent.tool_call.completed")
    'agent.tool_call.completed'
    >>> check_event_name("agent.did_stuff")
    Traceback (most recent call last):
        ...
    openagentx.workforce.ContractError: unknown workforce event name: agent.did_stuff
    """
    if name not in WORKFORCE_EVENTS:
        raise ContractError(f"unknown workforce event name: {name}")
    return name
