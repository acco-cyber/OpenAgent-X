"""Example 37 — the workforce assembly: eight specialists, one objective,
each in a small bounded portion.

Every agent the HYDRION ONE blueprint describes, as one assembled
workforce on the module surface: the roster with its ceilings and
allowlists, the least-privilege refusal (research cannot even ask about
shell), the capability router choosing a deployment for private data with
named reasons, a research task dispatched under a contract-capped budget
with a permission denial observed, the structured handoff research ->
writing, the independent qa verifier refusing self-verification, and the
whole assembly's event trail validated against the canonical vocabulary.

Prints ``OK 37_workforce_assembly`` at the end.
"""

from openagentx.workforce import (BudgetExhausted, BudgetLedger,
                                  ContractError, HandoffError, ModelCandidate,
                                  PROFILES, TIERS, TOOL_TIERS,
                                  check_event_name, check_permission,
                                  profiles, require_independent_verifier,
                                  route, validate_handoff, validate_result,
                                  validate_task)

# 1) the roster: eight specialists, least-privilege by construction
print("== the roster (blueprint §7) ==")
for p in profiles():
    print(f"  {p.agent_id:<9} v{p.version}  ceiling {p.permission_ceiling}  "
          f"tools {','.join(p.allowed_tools):<38} "
          f"budget {p.max_tool_calls} calls")
assert len(profiles()) == 8

# 2) least privilege, observed: research is read-only and cannot even ask
print("\n== least privilege, observed ==")
d = check_permission(PROFILES["research"], "shell")
print(f"  research x shell     -> allowed={d.allowed}  ({d.reason})")
assert not d.allowed and "allowlist" in d.reason
d2 = check_permission(PROFILES["research"], "search")
print(f"  research x search    -> allowed={d2.allowed}")
assert d2.allowed
d3 = check_permission(PROFILES["coding"], "prod_deploy")
print(f"  coding  x prod_deploy-> allowed={d3.allowed}  ({d3.reason})")
assert not d3.allowed and "allowlist" in d3.reason

# 3) the capability router: private data stays on the restricted deployment
print("\n== capability routing (blueprint §6) ==")
cloud = ModelCandidate("cloud/frontier",
                       frozenset({"vision", "tool_calling"}),
                       0.95, 0.99, 3.0, "standard")
cheap = ModelCandidate("cloud/cheap", frozenset({"tool_calling"}),
                       0.70, 0.98, 0.2, "standard")
local = ModelCandidate("local/vllm",
                       frozenset({"vision", "tool_calling"}),
                       0.62, 0.90, 0.4, "restricted")
dec = route(("vision", "tool_calling"), "private", [cloud, cheap, local])
for model_id, verdict, reason in dec.reasons:
    print(f"  {model_id:<15} {verdict:<9} {reason}")
print(f"  chosen={dec.chosen or '(none)'}  fallback={dec.fallback or '(none)'}")
assert dec.chosen == "local/vllm" and dec.fallback == ""
dec2 = route(("vision", "tool_calling"), "private", [cloud, cheap, local])
assert dec2 == dec, "routing must be deterministic"

# 4) dispatch: the task budget is capped by the contract, fail-closed
print("\n== dispatch under the contract (§5) ==")
task = {"task_id": "t-42", "objective": "sourced technical survey",
        "agent_id": "research",
        "budget": {"max_tool_calls": 3, "max_tokens": 2000},
        "acceptance_criteria": ["at least 8 primary sources"],
        "permission_scope": ["search", "fetch"]}
validate_task(task, PROFILES["research"])
print(f"  task accepted: budget {task['budget']['max_tool_calls']} calls "
      f"<= contract cap {PROFILES['research'].max_tool_calls}")
try:
    validate_task(dict(task, budget={"max_tool_calls": 50,
                                     "max_tokens": 2000}),
                  PROFILES["research"])
    raise SystemExit("a task must never exceed the contract cap")
except ContractError as e:
    print(f"  oversized budget refused: {e}")

# 5) the run: three tool calls through the ledger, one denial observed
print("\n== the run: budget ledger + permission gates ==")
ledger = BudgetLedger("research", 3)
for tool in ("search", "fetch", "read_file"):
    gate = check_permission(PROFILES["research"], tool)
    assert gate.allowed, gate.reason
    remaining = ledger.spend()
    print(f"  [agent.tool_call.completed] {tool:<10} remaining={remaining}")
try:
    gate = check_permission(PROFILES["research"], "shell")
    assert not gate.allowed
    ledger.spend()
    raise SystemExit("the ledger must fail closed at the cap")
except BudgetExhausted as e:
    print(f"  [agent.budget_exhausted]   {e}")
gate = check_permission(PROFILES["research"], "shell")
print(f"  [agent.permission_denied]  {gate.reason}")

# 6) the result: evidence before claims
print("\n== the result (evidence before claims) ==")
result = {"task_id": "t-42", "agent_id": "research", "status": "completed",
          "summary": "8 primary sources, 2 discarded as stale",
          "evidence_refs": [f"source:{i}" for i in range(1, 9)]}
validate_result(result, PROFILES["research"])
print(f"  completed with {len(result['evidence_refs'])} evidence refs")
try:
    validate_result(dict(result, evidence_refs=[]), PROFILES["research"])
    raise SystemExit("completed without evidence must be a violation")
except ContractError as e:
    print(f"  empty-evidence completion refused: {e}")

# 7) the handoff research -> writing, verified independently by qa
print("\n== collaboration (§7: structured handoffs, independent QA) ==")
handoff = {"from_agent": "research", "to_agent": "writing",
           "objective": "turn 8 sources into a sourced report",
           "acceptance_criteria": ["every claim carries a citation"],
           "artifact_refs": ["artifact:report-draft"]}
validate_handoff(handoff, PROFILES["research"], PROFILES["writing"])
print(f"  handoff accepted: research -> writing "
      f"({len(handoff['acceptance_criteria'])} acceptance criteria)")
gate = check_permission(PROFILES["writing"], "shell")
print(f"  writing x shell -> allowed={gate.allowed}  ({gate.reason})")
assert not gate.allowed and "allowlist" in gate.reason
require_independent_verifier("writing", "qa")
print("  verifier: qa verifies writing (independent)")
try:
    require_independent_verifier("writing", "writing")
    raise SystemExit("the producer cannot verify itself")
except HandoffError as e:
    print(f"  self-verification refused: {e}")

# 8) the assembly's event trail is canonical vocabulary, all of it
print("\n== the event trail (§12 vocabulary) ==")
trail = ["agent.started", "agent.model_selected", "agent.tool_call.started",
         "agent.tool_call.completed", "agent.permission_denied",
         "agent.budget_exhausted", "agent.completed", "handoff.accepted"]
for name in trail:
    print(f"  {check_event_name(name)}")
try:
    check_event_name("agent.did_stuff")
    raise SystemExit("invented event names must be rejected")
except ContractError as e:
    print(f"  invented name rejected: {e}")

print()
print("OK 37_workforce_assembly")
