# 12. Data model, APIs and event contracts

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 12. Adapted for OpenAgent-X.

## Core relational entities

| Entity/table | Key fields | Purpose |
| --- | --- | --- |
| users | id, email/subject, role, status, created_at | Identity mapping and account lifecycle. |
| projects | id, owner_id, name, policy_id, created_at | Project scope, instructions and membership boundary. |
| project_members | project_id, user_id, role | Project authorization. |
| tasks | id, project_id, creator_id, objective, state, risk, budget, created_at | Canonical task record. |
| subtasks | id, task_id, agent_id, dependency_refs, state, acceptance_criteria | Delegated work graph. |
| workflow_events | id, task_id, sequence, event_type, payload, timestamp | Append-only state and action history. |
| agent_definitions | id, version, capabilities, limits, tool_allowlist | Versioned agent catalog. |
| agent_runs | id, subtask_id, runtime_id, model_id, usage, status | Execution record. |
| model_deployments | id, provider, model, capabilities, cost, health | Provider/model registry. |
| tool_registry | id, server, tool_name, schema, risk, version | Tool catalog and policy metadata. |
| approvals | id, task_id, action_hash, approver_id, decision, expires_at | Human approval evidence. |
| artifacts | id, task_id, project_id, uri, mime_type, sha256, size | Generated and input files. |
| memories | id, project_id, domain, content, source_refs, confidence, status | Project/user knowledge records. |
| credentials_refs | id, owner_id, provider, secret_ref, scope | References to secret manager entries; never raw secrets. |
| evaluations | id, run_id, suite, metric, value, config_hash | Benchmark and quality results. |

## Public API surface (initial)

| Method + path | Purpose |
| --- | --- |
| POST /api/v1/tasks | Create a task and return task ID plus initial state. |
| GET /api/v1/tasks/{task_id} | Read task state, plan summary and progress. |
| POST /api/v1/tasks/{task_id}/approve | Approve an action or plan version by approval token. |
| POST /api/v1/tasks/{task_id}/cancel | Request cancellation and cleanup. |
| POST /api/v1/tasks/{task_id}/resume | Resume after an explicit blocker is resolved. |
| GET /api/v1/tasks/{task_id}/events | Read ordered workflow events. |
| GET /api/v1/tasks/{task_id}/artifacts | List downloadable artifacts. |
| GET /api/v1/projects/{project_id}/memory | Search permitted project memory. |
| POST /api/v1/projects/{project_id}/memory | Create a candidate or verified memory record. |
| GET /api/v1/models/capabilities | List available model capability profiles, subject to policy. |
| GET /api/v1/agents | List available agent definitions. |
| POST /api/v1/tools/{tool_id}/invoke | Internal tool-gateway endpoint; not directly exposed to untrusted clients. |

## Task creation request example

`POST /api/v1/tasks`

```json
{
  "project_id": "prj_123",
  "objective": "Review the repository and implement the CSV export feature",
  "constraints": {
    "max_cost_usd": 8,
    "deadline": null,
    "allow_external_write": false
  },
  "deliverables": ["code_patch", "test_report", "implementation_summary"],
  "attachments": ["artifact_456"]
}
```

## Event envelope

```json
{
  "event_id": "uuid",
  "task_id": "uuid",
  "sequence": 42,
  "event_type": "agent.tool_call.completed",
  "occurred_at": "2026-11-05T12:00:00Z",
  "actor": {"type": "agent", "id": "coding@1.0.0"},
  "correlation_id": "uuid",
  "payload": {"tool": "pytest", "exit_code": 0},
  "redaction_applied": true
}
```

## Event naming

- `task.created`, `task.planned`, `task.approval_requested`, `task.approved`, `task.started`.
- `subtask.dispatched`, `subtask.completed`, `subtask.failed`.
- `agent.started`, `agent.model_selected`, `agent.tool_call.started`, `agent.tool_call.completed`.
- `execution.workspace_created`, `execution.snapshot_created`, `execution.terminated`.
- `verification.started`, `verification.passed`, `verification.failed`.
- `artifact.created`, `artifact.downloaded`, `memory.candidate_created`, `memory.promoted`.
- `task.waiting_for_user`, `task.blocked`, `task.recovered`, `task.completed`, `task.failed`, `task.cancelled`.
