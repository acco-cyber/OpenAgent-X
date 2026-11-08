# Blueprint §13–17 — UX, technology stack, compute, monorepo, roadmap

*Faithful port of HYDRION ONE blueprint v1.0 (2026-11-05). Proposed plan, not
a claim of implemented capability.*

## 13. User experience and interface requirements

### Information architecture

| Screen | Required elements |
|---|---|
| Home / command center | Objective input, project selector, active tasks, recent artifacts, model/compute status and quick-start workflow templates. |
| Task workspace | Task objective, plan graph, live timeline, subtask owners, current action, approvals, cost/budget, logs and artifacts. |
| Plan review | Editable subtasks, dependencies, assumptions, risk labels, capability selection and approval controls. |
| Agent catalog | Agent capability cards, version, runtime, allowed tools, limits, reliability metrics and enable/disable. |
| Model control center | Provider connection health, aliases, capabilities, routing profiles, cost estimates, fallback behavior and usage. |
| Project memory | Search, sources, confidence, status, edit, pin, supersede, export and delete. |
| Workspace browser | Files, diffs, snapshots, terminal output and artifact history with path boundaries visible. |
| Security / approvals | Pending actions, destination, exact payload, risk, permission level, expiration and approve/deny. |
| Observability / admin | Errors, traces, usage, spend, queue depth, worker health, tool success and audit search. |

### Task timeline design

- Show each event with timestamp, actor, agent, model and status.
- Make tool calls expandable with sanitized arguments and outputs.
- Show which subtasks are parallel and which are blocked by dependencies.
- Separate model-generated reasoning summaries from verified facts and tool
  evidence. Do not display private chain-of-thought; show concise
  explanations, decisions and observable actions.
- Show cost and token usage at task and subtask level.
- Provide pause, cancel, retry and approval controls where state permits.
- Make artifacts first-class with type, checksum, created-by, source task and
  download action.

### Visual design guidance

- Dark navy / teal identity with high contrast and restrained accent colors.
- Prefer one primary objective input and a clear task canvas over a crowded
  dashboard.
- Use status colors consistently: neutral for queued, blue for running, amber
  for awaiting approval, red for blocked/failed, green for verified
  completion.
- Use expandable progressive disclosure for logs and tool payloads.
- Design every empty state with a clear next action and every error state
  with a recovery path.
- Support keyboard navigation, responsive layout, accessible labels and
  reduced-motion preferences.

### MVP interface acceptance

A user unfamiliar with the internal architecture must be able to submit a
task, inspect and modify the plan, approve an action, see progress, cancel a
run, inspect verification and download its artifacts without using the
terminal or reading raw backend logs.

## 14. Technology stack and deployment topology

| Area | Recommended choice | Reason / boundary |
|---|---|---|
| Frontend | Next.js + React + TypeScript | Strong product UI ecosystem, typed API client and accessible component patterns. |
| Desktop | Tauri, later | Native shell only after web workflow is stable; avoid duplicating the product UI. |
| Backend API | Python + FastAPI + Pydantic | Convenient AI/data ecosystem, typed validation and async service support. |
| Workflow engine | Temporal Python SDK for production durability; lightweight persisted state machine during earliest spike if needed. | Durable long-running jobs, activities, retries, timers and cancellation. [R12] |
| Model gateway | LiteLLM or comparable provider proxy + HYDRION policy router | Provider API normalization, load balancing and fallback primitives. [R8] |
| Coding runtime | OpenHands Software Agent SDK / Agent Server | Purpose-built coding agent execution and remote workspace interface. [R3, R4] |
| Tool protocol | MCP | Tool discovery and interoperability. Security still belongs to HYDRION. [R9, R10] |
| External agent protocol | A2A-compatible adapter | Interoperate with independent agents without coupling internal state. [R11] |
| Primary database | PostgreSQL | Transactional source of truth for users, projects, tasks, events and memory metadata. |
| Vector retrieval | pgvector | Vector search in PostgreSQL; add specialized vector DB only after scale/evaluation justifies it. |
| Cache / ephemeral coordination | Redis | Cache, short-lived locks, rate-limit counters and transient coordination. |
| Artifact storage | S3-compatible object store / MinIO | Durable artifacts, inputs, screenshots and run attachments. |
| Observability | OpenTelemetry + Prometheus/Grafana + centralized logs | Correlated traces, metrics and logs across model/tool/runtime boundaries. [R13] |
| Execution | Docker sandbox first; VM / Kubernetes-backed pools later | A simple security boundary for MVP; harden before exposing to untrusted tenants. |
| Inference | Cloud APIs plus Ollama/vLLM where compatible | Hybrid compute while keeping model hosting independent from orchestration. |

### Why not use every technology immediately?

NATS, Kafka, Neo4j, Kubernetes, Ray, a custom Rust daemon, a visual workflow
editor and a dozen agent runtimes are all plausible future tools. None should
be introduced before a measurable need exists. Start with PostgreSQL, a
durable workflow engine, Redis, object storage and Docker. A small number of
well-defined components is easier to secure, test and operate.

### Environment separation

| Environment | Purpose | Rules |
|---|---|---|
| Local development | UI, API, unit tests, mock models and local DB. | No production keys; seeded fake data; local test containers. |
| Integration / staging | Real providers with low-budget keys, test MCP servers and disposable workspaces. | Synthetic data only; isolated secrets; full traces. |
| Research / evaluation | Pinned models, datasets, benchmark harness and repeatable configs. | Version everything; separate experimental from product metrics. |
| Production | User projects and real tool credentials. | Approvals, strong auth, monitored egress, backups, SLOs and incident response. |

## 15. DGX Spark and compute strategy

The product should be model-agnostic and compute-aware. The laptop is a
development console; DGX Spark is the preferred local inference and
engineering compute node; cloud APIs and remote GPU instances are fallbacks
for workloads that exceed local memory, performance or software
compatibility. The official DGX Spark specification lists a Grace Blackwell
system, 128 GB coherent unified system memory in the 128 GB configuration,
273 GB/s memory bandwidth and up to 1 PFLOP FP4 theoretical performance with
sparsity. Actual model throughput depends on model architecture,
quantization, context length, software stack and workload. [R14]

### Role allocation

| Resource | Use | Avoid |
|---|---|---|
| Developer laptop (32 GB RAM, integrated graphics) | Editor, Git, browser, UI/API development, unit tests, docs, SSH and monitoring dashboards. | Assuming it can host large inference or multiple execution sandboxes. |
| DGX Spark | Local model serving, embeddings, evaluation jobs, code/data workloads that fit memory and supported software, private inference experiments. | Treating its theoretical FP4 number as guaranteed application throughput; exposing inference ports directly to the internet. |
| Cloud model APIs | High-quality reasoning, multimodal models and burst capacity. | Sending restricted project data without checking provider and data policy. |
| Remote GPU / cluster | Large models, large-batch evaluation, distributed training or workloads beyond DGX Spark. | Making Kubernetes/Ray mandatory for the MVP. |

### Compute scheduler inputs

- Required capability: text, vision, audio, embeddings, tool use, structured
  output.
- Model memory estimate and runtime compatibility.
- Available system memory / GPU memory, concurrency and queue depth.
- Task latency target, budget and expected tokens.
- Privacy classification and location/data-residency rule.
- Model health, quality evidence and benchmark history.
- Fallback endpoint and failure behavior.

### Local inference architecture

```text
HYDRION API / ORCHESTRATOR
  |
  v
MODEL ROUTER ---- cloud providers (policy-approved)
  |
  +---- DGX Spark gateway
  |       |
  |       +-- local model server (vLLM / supported runtime)
  |       +-- embeddings service
  |       +-- evaluation worker

Execution traffic is private-network only. Put model endpoints behind
an authenticated reverse proxy / network policy. Do not rely on a
single inference server API-key option as the complete security boundary.
```

vLLM documents an OpenAI-compatible HTTP server, but its own documentation
warns that API-key authentication does not cover every endpoint. Deploy
behind a reverse proxy, restrict network access, disable unused routes and
test the actual version in use. [R15]

### Compute rollout

1. Start with cloud APIs and mock endpoints so application development is not
   blocked by GPU setup.
2. Bring up one local model endpoint on DGX Spark and register it with the
   same model gateway.
3. Run a capability smoke test: streaming, structured output, tool calling,
   context, concurrency and cancellation.
4. Benchmark per-task latency, tokens/sec, peak memory, quality and failure
   rate under realistic context lengths.
5. Add embeddings and evaluation workers only after stable inference is
   achieved.
6. Implement queue-based admission control and graceful fallback when local
   capacity is unavailable.

## 16. Monorepo structure and engineering standards

Use a monorepo initially so API contracts, migrations, frontend, orchestration
and tests evolve together. Keep external runtimes independently versioned and
accessed through APIs or thin adapters. Split repositories only when
ownership, deployment or contribution scale requires it.

```text
hydrion-one/
  apps/
    web/               # Next.js user interface
    desktop/           # Tauri shell (later)
    cli/               # Optional operator/developer CLI
    admin/             # Admin and observability UI
  services/
    api/               # FastAPI public/internal APIs
    orchestrator/      # Durable workflows and planning
    model_gateway/     # Provider proxy + HYDRION router
    agent_registry/    # Versioned agent definitions
    memory/            # Memory and knowledge API
    tool_gateway/      # MCP clients, tool policy mediation
    execution/         # Sandbox lifecycle and runtime adapters
    artifacts/         # Artifact metadata and object-store access
    scheduler/         # Compute admission and queue policy
  agents/
    research/ coding/ data/ mathematics/ science/
    browser/ writing/ memory/ qa/
  integrations/
    providers/ openhands/ agent_zero/
    interpreter_workstation/ openagent/ mira/
    mcp/ a2a/ github/ notifications/
  packages/
    contracts/ schemas/ api_client/ ui_components/
    policy_sdk/ telemetry_sdk/ test_fixtures/
  security/
    auth/ policy/ secrets/ sandbox/ audit/
  evaluation/
    datasets/ harnesses/ task_suites/ reports/
  infrastructure/
    docker/ compose/ dgx_spark/ monitoring/ deployment/
  docs/
    architecture/ adr/ security/ operations/ research/
  scripts/ tests/ migrations/
  .github/ README.md CONTRIBUTING.md SECURITY.md LICENSE
```

### Engineering conventions

- Typed interfaces and schema validation at all service boundaries.
- Version every agent definition, tool adapter, model deployment alias and
  event schema.
- Keep business logic out of API route handlers.
- Use database migrations with rollback notes and integration tests.
- Use structured logging with task_id, project_id, trace_id and actor_id;
  redact secrets and private payloads.
- Add unit tests for policy decisions and state transitions; integration
  tests for runtime behavior.
- Every new external integration includes timeout, retry, rate limit, health
  check and license/security review.
- Pin dependencies and container digests for releases; generate SBOM and
  release checksums.
- Use feature flags for risky or incomplete capabilities.
- Document operational impact and failure modes in every architecture
  decision record.

### Branch and release pattern

Use short-lived feature branches, reviewed pull requests, required CI, signed
version tags and conventional release notes. Avoid direct pushes to the
protected main branch. Every PR should reference an issue or planned
acceptance criterion and include tests, screenshots for UI changes, migration
impact and risk notes.

## 17. 24-week implementation roadmap

The sequence below is a recommended build order, not a fixed promise. It
assumes a small team with consistent engineering time. If working solo,
extend the calendar rather than skipping security, verification or testing
gates.

| Week | Milestone | Build scope | Acceptance gate |
|---|---|---|---|
| W01 | Repository foundation | Create monorepo; define contribution rules; set up lint, tests, formatting, CI, secret scanning and docs. | Clean clone builds; CI runs on PR; no secrets committed. |
| W02 | API and identity skeleton | FastAPI app, typed settings, OIDC integration path, user/project tables, health endpoints. | Authenticated user can create and access an isolated project. |
| W03 | Model gateway | Provider adapter abstraction; integrate 3 endpoints; secrets references; request logging. | Smoke tests pass for each provider; model identity and usage recorded. |
| W04 | Minimal product shell | Next.js command center, project selector, task form, task history and API client. | User submits a request and sees persisted task record. |
| W05 | Task state machine | Implement canonical states, transitions, append-only events and cancellation model. | State transition tests cover legal and illegal transitions. |
| W06 | Planner and schema | Planner prompts, JSON schema, validation, assumptions, dependency graph and acceptance criteria. | Complex request creates a valid, inspectable plan. |
| W07 | Durable orchestration | Temporal workflow or persisted workflow worker; retries, deadlines, task recovery. | Service restart does not lose task state; duplicate dispatch is controlled. |
| W08 | Approval and policy service | Risk levels, P0-P4, action hashes, approval expiry, deny and audit. | A P3 action cannot execute without a matching approval. |
| W09 | Agent registry/contracts | Versioned definitions, AgentTask/AgentResult schemas, capability requirements and budgets. | At least 3 agent profiles register and validate. |
| W10 | Research agent | Search/fetch tools, source records, evidence output and report artifact. | Research task returns cited output with traceable sources. |
| W11 | Coding runtime adapter | Integrate OpenHands SDK/Agent Server in isolated environment; workspace create/terminate. | Agent modifies sample repo and returns a diff plus test log. |
| W12 | QA and verification | Independent verifier, test runner, acceptance criteria evaluation and failure classification. | Task cannot complete when required test/evidence check fails. |
| W13 | MCP tools | MCP client, allowlisted tool registry, schema validation and invocation audit. | One MCP server/tool can be connected and denied/approved by policy. |
| W14 | Artifact service | Object storage, checksums, downloads, provenance and retention metadata. | Task output artifact persists and can be downloaded securely. |
| W15 | Project memory MVP | PostgreSQL/pgvector, project-scoped ingestion, retrieval, provenance and correction. | A project decision is retrieved only inside its project ACL. |
| W16 | Task timeline UX | Live events, subtask progress, model/tool traces, approvals and artifacts. | User can monitor, cancel and inspect one full end-to-end task. |
| W17 | Data agent | Dataset profiling, bounded Python execution, reproducible script/notebook output. | Data workflow returns input profile, script and validation report. |
| W18 | Browser and computer boundary | Isolated browser context, screenshots, read-only default and user approval flow. | Browser research task works; sensitive action waits for approval. |
| W19 | DGX Spark integration | Local model gateway, health/queue, private endpoint and capability smoke suite. | Local model appears in registry and passes documented smoke tests. |
| W20 | Observability and operations | OpenTelemetry traces, metrics, logs, dashboards, backup and restore procedure. | End-to-end run is traceable across services; restore drill passes. |
| W21 | Security hardening | Threat-model review, sandbox quotas, egress filters, secrets audit, dependency scan. | No open critical finding; dangerous operations disabled by default. |
| W22 | Evaluation suite | Build golden tasks, regression harness, model/router comparison and cost accounting. | Reproducible baseline report with failures and configuration. |
| W23 | Release candidate | Installer/compose deployment, docs, onboarding, telemetry opt-in and SBOM. | Clean environment can deploy using documented steps. |
| W24 | Public release and research package | Release v0.1, demo, issues/roadmap, benchmark card, limitations and technical report. | Public demo and release artifacts match measured capability; known limits disclosed. |

### Release gates

| Gate | Must be true before proceeding |
|---|---|
| Gate A: vertical slice (end W08) | A user can create a task, generate a plan, approve a risk-gated action and inspect the durable state/event history. |
| Gate B: multi-agent execution (end W12) | Research and coding workers run through stable contracts; outputs are independently verified; task failure does not become false completion. |
| Gate C: usable MVP (end W16) | Task timeline, artifact service, memory and security controls form one coherent user experience. |
| Gate D: compute + secure execution (end W21) | DGX Spark endpoint is optional, execution is isolated, observability and incident controls are in place. |
| Gate E: public-grade v0.1 (end W24) | Evaluation is reproducible, docs are complete, security blockers are closed and claims are evidence-backed. |
