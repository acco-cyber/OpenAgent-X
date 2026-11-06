# 5. Orchestration engine and durable task lifecycle

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 5. Adapted for OpenAgent-X.

This is the most important OpenAgent-X-owned component. It turns a conversation into a persisted, inspectable workflow. The model may propose plans and reason about dependencies, but the orchestrator owns state transitions, scheduling, authorization, budgets, retries and terminal outcomes.

## Canonical task states

| State | Meaning | Allowed next states / rule |
| --- | --- | --- |
| CREATED | Request accepted and assigned a task ID. | PLANNED, CANCELLED, FAILED. |
| PLANNED | Plan and subtasks validated; budgets and permissions estimated. | APPROVED, RUNNING for fully pre-approved low-risk steps, WAITING_FOR_USER. |
| APPROVED | Required human approval captured and bound to a specific plan/action hash. | RUNNING, CANCELLED. |
| RUNNING | One or more activities are executing. | VERIFYING, WAITING_FOR_USER, BLOCKED, FAILED, CANCELLED, RECOVERY. |
| VERIFYING | Evidence, artifacts, tests and policy compliance are checked. | COMPLETED, RECOVERY, BLOCKED, FAILED. |
| WAITING_FOR_USER | An approval, missing input or user decision is required. | APPROVED, RUNNING, CANCELLED. |
| BLOCKED | Execution cannot proceed due to permission, dependency, environment or policy. | RUNNING after cause is resolved, CANCELLED, FAILED. |
| RECOVERY | A retry, replan or workspace restore is being performed. | RUNNING, BLOCKED, FAILED. |
| COMPLETED | All required acceptance checks passed. | Terminal. Corrections create a new task or an explicit revision. |
| FAILED | Task exhausted recovery policy or violated a hard constraint. | Terminal; user may create a new attempt. |
| CANCELLED | User or policy stopped the task. | Terminal; cleanup and audit still run. |

## Orchestration sequence

1. Receive user objective, identity, selected project and attached artifacts.
2. Normalize intent into a task specification. Preserve explicit constraints, date/time, output format and exclusions.
3. Estimate complexity, risk class, expected capabilities, budget and deadline.
4. Ask a clarifying question only when a missing detail blocks safe execution; otherwise choose a conservative default and expose it in the plan.
5. Generate a dependency graph of subtasks with acceptance criteria and required artifacts.
6. Validate task plan against permissions, policy, provider availability and resource budgets.
7. Obtain approval for high-risk or externally visible actions. Approval is bound to the exact action/plan version.
8. Dispatch eligible subtasks to agents using the registry and model router. Persist events before and after side effects.
9. Collect outputs and evidence. Run deterministic tests first; use independent QA for semantic checks.
10. If a check fails, classify failure and allow bounded retry or replan. Never repeat non-idempotent external actions without reconciliation.
11. Finalize deliverables, citations, costs, trace and user-visible limitations.
12. Persist final state and schedule cleanup of temporary workspaces and credentials.

## Planner output schema

```json
{
  "task_id": "uuid",
  "objective": "Build a sourced technical report",
  "assumptions": ["Use project workspace research-2026"],
  "constraints": {"deadline": null, "max_cost_usd": 5.0},
  "risk_level": "low|medium|high|critical",
  "subtasks": [
    {
      "subtask_id": "uuid",
      "objective": "Collect primary sources",
      "depends_on": [],
      "agent_type": "research",
      "required_capabilities": ["web_search", "source_citation"],
      "acceptance_criteria": ["At least 8 relevant primary sources"],
      "permission_scope": ["web.read"],
      "budget": {"max_tokens": 12000, "max_tool_calls": 25}
    }
  ],
  "final_deliverables": ["report.pdf", "sources.json"]
}
```

## Reliability rules

- Persist workflow intent and state before dispatching an activity.
- Use deterministic activity IDs and idempotency keys for side-effecting tools.
- Use at-least-once activity execution with idempotent handlers; do not assume exactly-once external side effects.
- Set maximum retries, timeouts, token budgets, tool-call budgets and maximum parallel subtasks.
- Use exponential backoff with jitter for retryable provider errors; do not retry invalid requests or permission denials.
- Store checkpoint artifacts and workspace snapshots before risky transformations.
- Cancellation must propagate to activities and trigger cleanup; if cancellation cannot stop an external action, record the unresolved action.
- Use human approval as a persisted state, not as a chat-only promise.

## Suggested initial limits

| Control | Initial policy (tune with evidence) |
| --- | --- |
| Concurrent subtasks | 2-4 per user task for MVP; cap total worker concurrency at service level. |
| Agent delegation depth | Maximum 2 levels initially: orchestrator -> specialist; specialist -> at most one bounded helper. |
| Retries | 2 retries for transient infrastructure errors; 1 retry with a revised prompt/approach for an agent failure; no retry for authorization denial. |
| Tool budget | Per-agent and per-task caps; low-risk research may be higher than write-enabled agents. |
| Timeout | Every provider call, tool call, workflow and execution container has a finite timeout. |
| Finalization | Task is COMPLETED only after required acceptance criteria are met or explicitly waived by a user with the waiver recorded. |
