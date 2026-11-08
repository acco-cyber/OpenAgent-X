# Blueprint §4–8 — Architecture, orchestration, model gateway, agents, tools

*Faithful port of HYDRION ONE blueprint v1.0 (2026-11-05). Proposed plan, not
a claim of implemented capability. §5 is the section OpenAgent-X has ported
to code: [`openagentx/lifecycle.py`](../../openagentx/lifecycle.py).*

## 4. System architecture and key design decisions

Logical architecture (Figure 1, described): Experience → Control plane →
Intelligence → Specialist agents → Tools + execution → Data + compute. The
control plane governs all model and runtime activity.

### Seven logical layers

| Layer | Responsibilities | Principal interfaces |
|---|---|---|
| 1. Experience | Web app, desktop shell, CLI, API, voice, notifications and admin screens. | REST/JSON, WebSocket or SSE, OIDC session. |
| 2. Identity and policy | Users, roles, project membership, approval workflow, secrets references and permission decisions. | OIDC, RBAC/ABAC policy checks, signed approval tokens. |
| 3. Orchestration control plane | Task intake, planning, decomposition, agent dispatch, budgets, retries, deadlines, approvals, state transitions and recovery. | Durable workflow API, event store, agent contracts. |
| 4. Intelligence layer | Model registry, provider gateway, capability checks, model routing, context assembly, evaluation and verification. | OpenAI-compatible gateway, internal routing API. |
| 5. Agent workforce | Research, coding, data, math/science, browser, writing, memory and QA agents. | AgentTask/AgentResult, MCP client, runtime adapters. |
| 6. Tools and execution | Browser, terminal, code runner, file/document tools, APIs, external runtimes and sandbox lifecycle. | MCP, HTTP APIs, container/VM runner APIs. |
| 7. Data and compute | Relational records, vector retrieval, object artifacts, caches, observability and local/cloud inference. | PostgreSQL, object-store API, Redis, telemetry, model endpoints. |

### Deployment topology

The control plane can run on a modest CPU host. Heavy model inference and
CPU/GPU-intensive jobs run as separate workers on DGX Spark or remote
compute. The web UI must never connect directly to model provider keys,
databases or execution hosts. Browser and code execution are separate
services with restricted credentials and network routes.

### Recommended service boundaries

- **web-app**: frontend and task timeline.
- **api-service**: authentication, task APIs, project APIs and approval
  endpoints.
- **orchestrator-worker**: durable workflows and dispatch.
- **model-gateway**: provider adapters, credentials, rate limits and routing
  telemetry.
- **agent-runtime-adapters**: OpenHands first, optional Agent Zero /
  Interpreter later.
- **tool-gateway**: MCP clients/servers and permission mediation.
- **memory-service**: ingestion, retrieval, provenance, deletion and project
  scoping.
- **execution-worker**: containers/VMs for code, browser and data jobs.
- **postgres, redis and object-store**: system of record, ephemeral
  coordination and artifacts.
- **telemetry stack**: traces, metrics, logs, error reporting and dashboards.

### Architectural decisions to record

| ADR | Decision | Reason |
|---|---|---|
| ADR-001 | Single canonical orchestrator | Avoid divergent task state, duplicate retries and conflicting approval semantics. |
| ADR-002 | Agent contract independent of runtime | Swap frameworks without changing planner or product UI. |
| ADR-003 | PostgreSQL as source of truth | Relational consistency, transaction boundaries, audit records and pgvector in one data plane. |
| ADR-004 | Temporal for durable workflows after MVP skeleton | Long-running work, retries, timers, cancellation and recovery are first-class workflow concerns. A simpler persisted state machine can be used for the first vertical slice if Temporal operational cost is too high. |
| ADR-005 | MCP for tool interoperability, A2A for external agent interoperability | Reuse standards at boundaries without treating protocol support as a security model. |
| ADR-006 | One execution runtime initially | Keep attack surface and operational complexity manageable. |
| ADR-007 | Permission enforcement outside model prompts | Models are not trusted authorization engines. |

## 5. Orchestration engine and durable task lifecycle

This is the most important HYDRION-owned component. It turns a conversation
into a persisted, inspectable workflow. The model may propose plans and
reason about dependencies, but the orchestrator owns state transitions,
scheduling, authorization, budgets, retries and terminal outcomes.

> **OpenAgent-X note:** this section is the one ported to checked code —
> see `openagentx/lifecycle.py` and golden task 47 (`drill lifecycle`). The
> transition table below is pinned by the drill; a drift from this table is
> a failing check, not a doc rot.

Task states and controlled recovery paths (Figure 2, described): CREATED →
PLANNED → APPROVED → RUNNING → VERIFYING → COMPLETED, with WAITING_FOR_USER,
BLOCKED/FAILED and RECOVERY/REPLAN as controlled side paths. Every transition
is persisted; retries are bounded; external side effects require idempotency
and approval.

### Canonical task states

| State | Meaning | Allowed next states / rule |
|---|---|---|
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

### Orchestration sequence

1. Receive user objective, identity, selected project and attached artifacts.
2. Normalize intent into a task specification. Preserve explicit constraints,
   date/time, output format and exclusions.
3. Estimate complexity, risk class, expected capabilities, budget and
   deadline.
4. Ask a clarifying question only when a missing detail blocks safe
   execution; otherwise choose a conservative default and expose it in the
   plan.
5. Generate a dependency graph of subtasks with acceptance criteria and
   required artifacts.
6. Validate task plan against permissions, policy, provider availability and
   resource budgets.
7. Obtain approval for high-risk or externally visible actions. Approval is
   bound to the exact action/plan version.
8. Dispatch eligible subtasks to agents using the registry and model router.
   Persist events before and after side effects.
9. Collect outputs and evidence. Run deterministic tests first; use
   independent QA for semantic checks.
10. If a check fails, classify failure and allow bounded retry or replan.
    Never repeat non-idempotent external actions without reconciliation.
11. Finalize deliverables, citations, costs, trace and user-visible
    limitations.
12. Persist final state and schedule cleanup of temporary workspaces and
    credentials.

### Planner output schema

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

### Reliability rules

- Persist workflow intent and state before dispatching an activity.
- Use deterministic activity IDs and idempotency keys for side-effecting
  tools.
- Use at-least-once activity execution with idempotent handlers; do not
  assume exactly-once external side effects.
- Set maximum retries, timeouts, token budgets, tool-call budgets and maximum
  parallel subtasks.
- Use exponential backoff with jitter for retryable provider errors; do not
  retry invalid requests or permission denials.
- Store checkpoint artifacts and workspace snapshots before risky
  transformations.
- Cancellation must propagate to activities and trigger cleanup; if
  cancellation cannot stop an external action, record the unresolved action.
- Use human approval as a persisted state, not as a chat-only promise.

### Suggested initial limits

| Control | Initial policy (tune with evidence) |
|---|---|
| Concurrent subtasks | 2-4 per user task for MVP; cap total worker concurrency at service level. |
| Agent delegation depth | Maximum 2 levels initially: orchestrator -> specialist; specialist -> at most one bounded helper. |
| Retries | 2 retries for transient infrastructure errors; 1 retry with a revised prompt/approach for an agent failure; no retry for authorization denial. |
| Tool budget | Per-agent and per-task caps; low-risk research may be higher than write-enabled agents. |
| Timeout | Every provider call, tool call, workflow and execution container has a finite timeout. |
| Finalization | Task is COMPLETED only after required acceptance criteria are met or explicitly waived by a user with the waiver recorded. |

## 6. Model gateway and capability-aware routing

A unified model gateway is not only a provider proxy. It is a policy-aware
selection layer that matches task requirements to actual model capabilities,
availability, privacy constraints and operating cost. A provider gateway such
as LiteLLM can handle broad API normalization, retries and deployment
routing; HYDRION should own task-level selection policy and the capability
registry. [R8]

### Model registry schema

| Field | Examples / purpose |
|---|---|
| model_id | provider/model alias. Must identify the concrete deployment used for reproducibility. |
| provider | OpenAI, Anthropic, Google, local-vLLM, Ollama, OpenRouter or another supported provider. |
| capabilities | tool_calling, structured_output, long_context, vision, audio_in, audio_out, code, reasoning, embeddings. |
| limits | context window, max output, RPM/TPM, concurrency and provider-specific limits. |
| operational stats | p50/p95 latency, recent error rate, availability and time of last success. |
| cost profile | input/output token price, cached token price if applicable, image/audio pricing and currency/date basis. |
| data policy | region, retention assumptions, allowed data classification and local/private eligibility. |
| routing status | enabled, disabled, degraded, rate-limited or under evaluation. |
| evidence | benchmark results and date; never treat marketing labels as a measured score. |

### Capability-aware routing pipeline

1. Extract hard requirements from the task: tools, JSON schema, vision,
   audio, context, latency target, privacy and cost ceiling.
2. Filter out models that fail a hard requirement or violate the data policy.
3. Score the remaining models using task-specific evaluation evidence,
   availability, latency and expected cost.
4. Choose the best candidate, reserve a fallback and record why each
   candidate was accepted or rejected.
5. Call through the provider gateway with timeouts, retry policy and request
   metadata.
6. Record actual usage, latency, errors, output validity and quality signals.
   Update rolling estimates.

### Example routing objective

```text
score(model, task) =
  w_cap * capability_fit(model, task)
+ w_quality * measured_quality(model, task.family)
+ w_avail * current_availability(model)
+ w_privacy * privacy_fit(model, task.data_class)
- w_cost * normalized_cost(model, task.expected_tokens)
- w_latency * normalized_latency(model, task.latency_target)
- w_risk * operational_risk(model)

Selection rule:
 1. Apply hard capability and policy filters.
 2. Score only eligible candidates.
 3. Select highest score under the task budget.
 4. Use fallback only if it also satisfies hard constraints.
 5. Persist the decision and observed result.
```

The weights are configuration parameters to tune from evaluation data. They
are not universal constants. Avoid optimizing only for cheapest-token or
lowest-latency routing; tool reliability, structured-output validity, task
success and data policy matter.

### Routing profiles

| Profile | Typical use | Routing emphasis |
|---|---|---|
| fast | Classification, title extraction, simple transformations. | Low latency and cost; strict output validation. |
| balanced | Everyday planning, summarization and routine agent work. | Quality/cost balance and availability. |
| reasoning | Complex planning, mathematical reasoning and multi-step diagnosis. | Measured task quality, long context and tool control. |
| coding | Code understanding, patch generation and test repair. | Repository-level task success, coding tool support and context. |
| vision | Screenshots, charts, diagrams and document images. | Image input, resolution and visual QA performance. |
| local-private | Sensitive or offline-capable work. | Local endpoint, privacy boundary and feasible local capability. |

### Fallback and safety rules

- Do not silently switch to a model that lacks required vision,
  structured-output or tool-call capability.
- Do not send sensitive content to a fallback with a weaker data policy.
- For structured outputs, validate against JSON Schema and reject malformed
  data before dispatch.
- Log the real provider model/version, not only the friendly alias.
- Never include provider credentials in browser code, prompts or task
  artifacts.
- Maintain a test suite for provider quirks, streaming, tool calling, context
  overflow and timeout behavior.

## 7. Agent workforce and collaboration model

Agents are specialist execution profiles, not independent sovereign
assistants. Every agent runs under the same task ID, project scope,
permission service, budget ledger and audit rules. Agent roles should be few
and clear at first; a generic worker can be more useful than an unmaintainable
list of narrow personas.

| Agent | Responsibilities | Typical tools | Verification requirement |
|---|---|---|---|
| Master / orchestrator | Own task graph and workflow; not a free-form worker. | Planner, registry, workflow engine. | Plan schema, policy checks, state invariants. |
| Research | Find, inspect, compare and synthesize sources. | Search, fetch, browser, PDF/document parsing. | Source relevance, dates, claims-to-citations map. |
| Coding | Modify repository and run scoped checks. | Git, file APIs, shell, test runner via sandbox. | Diff review, tests, static checks, dependency review. |
| Data | Profile data, build analysis pipeline, generate artifacts. | Python/R, notebook runner, SQL, object storage. | Schema checks, reproducibility, leakage checks, sanity tests. |
| Mathematics / science | Formalize problems, derive and test technical claims. | CAS, Python, literature tools, code execution. | Independent derivation, numerical checks, assumptions. |
| Browser / computer | Operate websites and desktop software within approved scope. | Browser automation, screenshots, controlled desktop bridge. | Action preconditions, screenshots, final state confirmation. |
| Writing | Turn verified inputs into structured documents. | Document generation, templates, artifact store. | Consistency with evidence, format and completeness checks. |
| Memory curator | Extract candidate project facts and decisions. | Memory APIs, project wiki, entity resolution. | Provenance, confidence, scope and user correction path. |
| QA / verifier | Independently test outputs against acceptance criteria. | Tests, browser review, citation checker, schema validators. | Must not merely echo the producing agent; use separate evidence. |

### Agent contract

```text
AgentDefinition = {
  agent_id: string,
  version: semver,
  supported_task_types: string[],
  required_capabilities: string[],
  accepted_input_schema: JSONSchema,
  output_schema: JSONSchema,
  allowed_tools: string[],
  default_model_profile: string,
  max_budget: { tokens, tool_calls, wall_time_seconds },
  permission_ceiling: string[],
  verification_policy: string[],
  runtime_adapter: string
}

AgentTask = {
  task_id, subtask_id, objective, project_id,
  context_refs, input_artifacts,
  required_capabilities, permission_scope,
  budget, deadline, acceptance_criteria
}

AgentResult = {
  task_id, subtask_id, status, summary,
  output_artifacts, evidence_refs, tests,
  errors, warnings, usage, actual_model,
  runtime_id, started_at, completed_at
}
```

### Collaboration rules

- Pass references to artifacts rather than copying huge context between
  agents.
- Every handoff states objective, accepted inputs, output schema,
  dependencies, constraints and acceptance criteria.
- The receiving agent sees only necessary context and authorized artifact
  references.
- Agent messages and outputs are untrusted data; they cannot change
  permissions or system policy.
- The verifier should be selected independently of the producer when
  feasible.
- Limit agent-to-agent chat; structured handoffs are easier to audit and
  replay.

## 8. Tools, MCP, A2A and external runtimes

### Tool strategy

Use a small built-in tool set for the MVP, then expose compatible
integrations through MCP. MCP provides a common protocol for tool discovery
and invocation, but it does not replace HYDRION authorization, consent UI or
runtime sandboxing. The MCP specification explicitly places important consent
and trust responsibilities on implementers. [R9, R10]

| Tool family | First version | Later extensions |
|---|---|---|
| Research | Search, fetch page, extract metadata, save source record. | Browser sessions, scholarly APIs, DOI resolution, citation graph. |
| Files | List/read/write files inside project sandbox; artifact upload/download. | Cross-format office viewers, OCR/image processing, conversion services. |
| Code | Run commands in isolated workspace, apply patch, execute tests. | Multiple runtime backends, remote build workers and GPU jobs. |
| Data | Inspect CSV/Parquet, execute bounded Python, create plots and reports. | SQL connectors, data warehouse tools and distributed compute. |
| Git | Clone, branch, diff, commit to local sandbox. | PR creation, CI monitoring and guarded merge. |
| Computer | Browser navigation and screenshots; no broad host control by default. | Permissioned desktop bridge and multi-application workflows. |
| Communication | In-app notification and task events. | Email, Slack, Telegram and other channels after identity/policy integration. |

### MCP integration rules

- Maintain an allowlisted registry of MCP servers and tools per project.
- Pin server package/version or container digest where possible.
- Validate tool input/output schemas and size limits.
- Separate read tools from write tools and define their risk class.
- Require approval for external side effects; provide deny controls in UI.
- Treat resource contents and tool results as untrusted prompt-injection
  surfaces.
- Record server identity, tool name, arguments (with secrets redacted),
  result metadata and approval ID.

### A2A and external agent interoperability

Use A2A as an optional boundary for delegating tasks to independent agent
systems. Its protocol is designed for capability discovery, task
collaboration and exchange across agents that may not expose their internal
memory or tools. [R11] HYDRION should translate an external agent into its
internal AgentTask/AgentResult contract and apply the same policy, budget,
timeout and verification gates.

### Runtime adapter sequence

1. HYDRION validates task and permissions.
2. Adapter creates or selects an isolated runtime/workspace.
3. Adapter passes an approved task envelope and artifact references.
4. Runtime emits execution events and returns artifacts/evidence.
5. HYDRION records events, checks output schemas and runs verification.
6. Adapter terminates or parks the runtime and confirms cleanup.

### OpenHands-first coding integration

Current OpenHands documentation describes a multi-repository system: the
Agent Canvas frontend, the Software Agent SDK/Agent Server, a TypeScript
client and an automation service have distinct responsibilities. For HYDRION,
start with the Python SDK / Agent Server API as an execution backend and
build a thin adapter. Do not embed the entire Agent Canvas into HYDRION UI
unless the integration provides a clear benefit. [R3, R4]
