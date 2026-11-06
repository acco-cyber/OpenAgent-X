# 4. System architecture and key design decisions

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 4. Adapted for OpenAgent-X.

Figure 1 (Logical architecture): the control plane governs all model and runtime activity.

## Seven logical layers

| Layer | Responsibilities | Principal interfaces |
| --- | --- | --- |
| 1. Experience | Web app, desktop shell, CLI, API, voice, notifications and admin screens. | REST/JSON, WebSocket or SSE, OIDC session. |
| 2. Identity and policy | Users, roles, project membership, approval workflow, secrets references and permission decisions. | OIDC, RBAC/ABAC policy checks, signed approval tokens. |
| 3. Orchestration control plane | Task intake, planning, decomposition, agent dispatch, budgets, retries, deadlines, approvals, state transitions and recovery. | Durable workflow API, event store, agent contracts. |
| 4. Intelligence layer | Model registry, provider gateway, capability checks, model routing, context assembly, evaluation and verification. | OpenAI-compatible gateway, internal routing API. |
| 5. Agent workforce | Research, coding, data, math/science, browser, writing, memory and QA agents. | AgentTask/AgentResult, MCP client, runtime adapters. |
| 6. Tools and execution | Browser, terminal, code runner, file/document tools, APIs, external runtimes and sandbox lifecycle. | MCP, HTTP APIs, container/VM runner APIs. |
| 7. Data and compute | Relational records, vector retrieval, object artifacts, caches, observability and local/cloud inference. | PostgreSQL, object-store API, Redis, telemetry, model endpoints. |

## Deployment topology

The control plane can run on a modest CPU host. Heavy model inference and CPU/GPU-intensive jobs run as separate workers on DGX Spark or remote compute. The web UI must never connect directly to model provider keys, databases or execution hosts. Browser and code execution are separate services with restricted credentials and network routes.

## Recommended service boundaries

- `web-app`: frontend and task timeline.
- `api-service`: authentication, task APIs, project APIs and approval endpoints.
- `orchestrator-worker`: durable workflows and dispatch.
- `model-gateway`: provider adapters, credentials, rate limits and routing telemetry.
- `agent-runtime-adapters`: OpenHands first, optional Agent Zero / Interpreter later.
- `tool-gateway`: MCP clients/servers and permission mediation.
- `memory-service`: ingestion, retrieval, provenance, deletion and project scoping.
- `execution-worker`: containers/VMs for code, browser and data jobs.
- `postgres`, `redis` and `object-store`: system of record, ephemeral coordination and artifacts.
- `telemetry stack`: traces, metrics, logs, error reporting and dashboards.

## Architectural decisions to record (ADR)

| ADR | Decision | Reason |
| --- | --- | --- |
| ADR-001 | Single canonical orchestrator | Avoid divergent task state, duplicate retries and conflicting approval semantics. |
| ADR-002 | Agent contract independent of runtime | Swap frameworks without changing planner or product UI. |
| ADR-003 | PostgreSQL as source of truth | Relational consistency, transaction boundaries, audit records and pgvector in one data plane. |
| ADR-004 | Temporal for durable workflows after MVP skeleton | Long-running work, retries, timers, cancellation and recovery are first-class workflow concerns. A simpler persisted state machine can be used for the first vertical slice if Temporal operational cost is too high. |
| ADR-005 | MCP for tool interoperability, A2A for external agent interoperability | Reuse standards at boundaries without treating protocol support as a security model. |
| ADR-006 | One execution runtime initially | Keep attack surface and operational complexity manageable. |
| ADR-007 | Permission enforcement outside model prompts | Models are not trusted authorization engines. |
