# Agentic Mode — Operating Protocols

How an AI reaches **full agentic potential** inside OpenAgent-X while **reducing cost and raising reliability**. These protocols are normative: agents that follow them produce verifiable work; agents that don't produce confident guesses.

## The protocols

| # | Protocol | Purpose |
|---|---|---|
| 1 | [Planning protocol](01-planning-protocol.md) | Turn any objective into a schema-valid, budgeted, dependency-ordered plan |
| 2 | [Verification protocol](02-verification-protocol.md) | Make completion claims impossible without evidence |
| 3 | [Cost optimization](03-cost-optimization.md) | Cut token/tool spend 5-10x via profile ladders, budgets, context compression |
| 4 | [Safety protocol](04-safety-protocol.md) | Permission tiers, approval flow, injection defense |
| 5 | [Prompt pack](05-prompt-pack.md) | Copy-adapt system prompts for every agent role |

## The one-loop summary

```
objective
  → PLAN      cheapest sufficient thinking; schema-valid plan; budgets on every subtask
  → APPROVE   human hash-bound approval for P3+; conservative defaults exposed
  → DISPATCH  eligible subtasks to budgeted specialists; events persisted around side effects
  → EXECUTE   tool allowlists only; artifact references passed, not copied
  → VERIFY    deterministic checks first; independent QA second; failures classified
  → DELIVER   artifacts + evidence + costs + limitations; orchestrator sets COMPLETED
```

## Why this unlocks "100% potential"

Autonomy fails at four points: **planning drift, unverified success, runaway cost, and unsafe action**. Each protocol eliminates one failure mode:

- Planning drift → schema-validated plans with explicit assumptions and dependency graphs.
- Unverified success → acceptance criteria + independent verifier; confident answers are not evidence.
- Runaway cost → hard budgets per subtask + cheap-first routing + escalation ladders.
- Unsafe action → default-deny permissions + hash-bound approvals + sandboxed execution.

An AI that internalizes these four moves can be given **more autonomy**, not less — because every increase in freedom is bounded by a checkable contract.
