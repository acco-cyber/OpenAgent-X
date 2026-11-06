# 18. Detailed build sequence and acceptance gates

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 18. Adapted for OpenAgent-X.

## First 10 engineering tickets

### H1-001: Create repository and CI

- Files: README.md, pyproject.toml, package.json, .github/workflows/ci.yml, apps/web, services/api, docs/adr.
- Acceptance: fresh clone installs; formatting, lint and basic tests run; secret scanning enabled.

### H1-002: Define shared identifiers and schemas

- Files: packages/contracts/task.py, agent.py, event.py, artifact.py.
- Acceptance: Pydantic models validate; JSON schema is exported; schema tests cover invalid payloads.

### H1-003: Create database migrations

- Tables: users, projects, project_members, tasks, workflow_events, artifacts.
- Acceptance: migrations apply and rollback in test DB; tenant/project boundary tests pass.

### H1-004: Implement task API

- Endpoints: POST /tasks, GET /tasks/{id}, GET /tasks/{id}/events, POST /tasks/{id}/cancel.
- Acceptance: authenticated owner can create/read/cancel task; unauthorized user receives denial.

### H1-005: Implement provider adapter

- Provider interface: complete, stream, health, usage metadata, structured output.
- Acceptance: fake provider tests plus 3 real provider smoke tests; secrets never appear in logs.

### H1-006: Build model registry

- Files: services/model_gateway/registry.py, capabilities.py, routing.py.
- Acceptance: capability filter excludes incompatible model; selected model and reason are recorded.

### H1-007: Planner schema and validator

- Files: services/orchestrator/planner.py, plan_schema.json, plan_validator.py.
- Acceptance: invalid dependency graph rejected; budget and permission fields are mandatory.

### H1-008: Durable workflow skeleton

- Files: services/orchestrator/workflows/task_workflow.py, activities.py, worker.py.
- Acceptance: restart/resume and bounded retry tests pass.

### H1-009: Policy and approval service

- Files: security/policy/decision.py, approvals.py, tests.
- Acceptance: P3 invocation blocked until exact action-hash approval is valid.

### H1-010: First vertical slice

- Flow: user request -> plan -> approve -> mock tool -> verify -> artifact -> completed.
- Acceptance: end-to-end test checks UI/API, state transitions, event trail and downloadable artifact.

## Do not start these too early

- Do not create 10 specialist agents before the generic agent contract and one real workflow are stable.
- Do not build a visual workflow editor before state semantics and retry behavior are settled.
- Do not integrate all five reference runtimes at once.
- Do not implement automatic memory promotion before provenance and correction UI work.
- Do not expose host computer access before sandbox and approval gates are tested.
- Do not optimize model routing before baseline quality/cost measurements exist.

## Day-one engineering checklist

- Create the GitHub repository with a clear README, license decision, issue templates and security policy.
- Create architecture/decisions.md and record the first ADRs listed in Section 4.
- Choose Python and TypeScript versions based on the deployment environment and pin them.
- Create a local compose stack for PostgreSQL, Redis and object storage.
- Build health/readiness endpoints and structured logs.
- Add an integration-test environment using fake provider responses.
- Create one sample project and one scripted end-to-end task.
