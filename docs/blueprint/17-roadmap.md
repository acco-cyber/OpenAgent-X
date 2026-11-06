# 17. 24-week implementation roadmap

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 17. Adapted for OpenAgent-X.

## Recommended build order

The sequence below is a recommended build order, not a fixed promise. It assumes a small team with consistent engineering time. If working solo, extend the calendar rather than skipping security, verification or testing gates.

| Week | Milestone | Build scope | Acceptance gate |
|------|-----------|-------------|-----------------|
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

## Release gates

| Gate | Must be true before proceeding |
|------|-------------------------------|
| Gate A: vertical slice (end W08) | A user can create a task, generate a plan, approve a risk-gated action and inspect the durable state/event history. |
| Gate B: multi-agent execution (end W12) | Research and coding workers run through stable contracts; outputs are independently verified; task failure does not become false completion. |
| Gate C: usable MVP (end W16) | Task timeline, artifact service, memory and security controls form one coherent user experience. |
| Gate D: compute + secure execution (end W21) | DGX Spark endpoint is optional, execution is isolated, observability and incident controls are in place. |
| Gate E: public-grade v0.1 (end W24) | Evaluation is reproducible, docs are complete, security blockers are closed and claims are evidence-backed. |
