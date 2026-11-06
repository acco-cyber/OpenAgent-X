# Protocol 1 — Planning

Goal: convert any objective into a **schema-valid plan** (`schemas/plan.schema.json`) with explicit assumptions, acyclic dependencies, and budgets. The model proposes; the orchestrator validates.

## The 12-step sequence

1. **Receive** objective, identity, project, attached artifacts.
2. **Normalize** intent into a task specification — preserve explicit constraints, date/time, output format, exclusions verbatim.
3. **Estimate** complexity, risk class (P-tier), expected capabilities, budget, deadline.
4. **Clarify only when a missing detail blocks safe execution**; otherwise choose a conservative default *and expose it in the plan* (`assumptions[]`).
5. **Decompose** into a dependency graph of subtasks, each with acceptance criteria and required artifacts.
6. **Validate** the plan against permissions, policy, provider availability, resource budgets.
7. **Obtain approval** for high-risk or externally visible actions — bound to the exact plan/action hash.
8. **Dispatch** eligible subtasks to agents via registry + router. Persist events *before and after* side effects.
9. **Collect** outputs and evidence — deterministic tests first, independent QA for semantics.
10. **Classify failures**; bounded retry or replan. Never repeat non-idempotent external actions without reconciliation.
11. **Finalize** deliverables, citations, costs, trace, user-visible limitations.
12. **Persist** final state; schedule cleanup of temporary workspaces and credentials.

## Decomposition rules

- **3–7 subtasks** for a moderate objective. More than 7 means you're planning two levels too early — decompose the decompositions.
- Every subtask gets: objective (verb-first), `depends_on[]` (acyclic!), `agent_type`, `required_capabilities`, `acceptance_criteria[]` (checkable, not vibes), `permission_scope[]` (minimum needed), `budget` (tokens + tool calls).
- **Parallelize what's independent**; serialize only real dependencies. Fan out read-only research, fan in synthesis.
- Subtask independence test: could this run without seeing the others' outputs? If yes → parallel.
- Every assumption is written down. Silent assumptions become silent failures.

## Acceptance criteria rules

Write criteria a *different* agent can check mechanically:

| Bad (vibe) | Good (checkable) |
|---|---|
| "Good research" | "≥8 relevant primary sources, each with URL + date, ≥2 published within 12 months" |
| "Working feature" | "`npm test -- csv-export` passes; diff touches ≤6 files; no new deps without review note" |
| "Clean analysis" | "Notebook runs top-to-bottom without error; output CSV has 0 null rows in key column; chart artifacts attached" |

## Planner output contract

The planner emits exactly the `plan.schema.json` shape:

```json
{
  "task_id": "uuid",
  "objective": "Build a sourced technical report",
  "assumptions": ["Use project workspace research-2026"],
  "constraints": { "deadline": null, "max_cost_usd": 5.0 },
  "risk_level": "low",
  "subtasks": [{
    "subtask_id": "uuid",
    "objective": "Collect primary sources",
    "depends_on": [],
    "agent_type": "research",
    "required_capabilities": ["web_search", "source_citation"],
    "acceptance_criteria": ["At least 8 relevant primary sources"],
    "permission_scope": ["web.read"],
    "budget": { "max_tokens": 12000, "max_tool_calls": 25 }
  }],
  "final_deliverables": ["report.pdf", "sources.json"]
}
```

## Limits that make plans safe

| Control | Initial policy (tune with evidence) |
|---|---|
| Concurrent subtasks | 2–4 per user task; service-level worker cap |
| Delegation depth | Max 2: orchestrator → specialist → ≤1 bounded helper |
| Retries | 2 transient infra; 1 revised-prompt agent retry; 0 for auth denials |
| Tool budget | Per-agent + per-task caps; read-only work gets more than write-enabled work |
| Timeout | Finite on every provider call, tool call, workflow, container |
| Finalization | COMPLETED only when acceptance criteria met or explicitly waived (waiver recorded) |
