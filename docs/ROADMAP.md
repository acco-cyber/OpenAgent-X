# OpenAgent-X Roadmap

Build order adapted from blueprint §17. **The sequence is a recommended order, not a fixed promise** — if working solo, extend the calendar rather than skipping security, verification, or testing gates.

## Build order

| Week | Milestone | Build scope | Acceptance gate |
|---|---|---|---|
| W01 | Repository foundation | Monorepo, contribution rules, lint/tests/format, CI, secret scanning, docs | Clean clone builds; CI runs on PR; no secrets committed |
| W02 | API & identity skeleton | FastAPI app, typed settings, OIDC path, user/project tables, health endpoints | Authenticated user can create/access an isolated project |
| W03 | Model gateway | Provider adapter abstraction; 3 endpoints; secrets references; request logging | Smoke tests pass per provider; model identity + usage recorded |
| W04 | Minimal product shell | Next.js command center, project selector, task form, history, API client | User submits a request and sees persisted task record |
| W05 | Task state machine | Canonical states, transitions, append-only events, cancellation | State transition tests cover legal and illegal transitions |
| W06 | Planner & schema | Planner prompts, JSON schema, validation, assumptions, dependency graph | Complex request creates a valid, inspectable plan |
| W07 | Durable orchestration | Workflow worker; retries, deadlines, task recovery | Restart loses no task state; duplicate dispatch controlled |
| W08 | Approval & policy service | Risk levels P0–P4, action hashes, approval expiry, deny + audit | A P3 action cannot execute without matching approval |
| W09 | Agent registry/contracts | Versioned definitions, AgentTask/AgentResult, capability requirements, budgets | ≥3 agent profiles register and validate |
| W10 | Research agent | Search/fetch tools, source records, evidence output, report artifact | Research task returns cited output with traceable sources |
| W11 | Coding runtime adapter | OpenHands SDK/Agent Server in isolated env; workspace create/terminate | Agent modifies sample repo; returns diff + test log |
| W12 | QA & verification | Independent verifier, test runner, criteria evaluation, failure classification | Task cannot complete when required test/evidence check fails |
| W13 | MCP tools | MCP client, allowlisted tool registry, schema validation, invocation audit | One MCP server/tool connectable; denied/approved by policy |
| W14 | Artifact service | Object storage, checksums, downloads, provenance, retention | Task output artifact persists and downloads securely |
| W15 | Project memory MVP | PostgreSQL/pgvector, project-scoped ingestion, retrieval, provenance, correction | A decision is retrieved only inside its project ACL |
| W16 | Task timeline UX | Live events, subtask progress, model/tool traces, approvals, artifacts | User can monitor, cancel, inspect one full end-to-end task |
| W17 | Data agent | Dataset profiling, bounded Python, reproducible script/notebook | Data workflow returns profile, script, validation report |
| W18 | Browser & computer boundary | Isolated browser context, screenshots, read-only default, approval flow | Browser research works; sensitive action waits for approval |
| W19 | DGX Spark integration | Local model gateway, health/queue, private endpoint, capability smoke suite | Local model in registry passes documented smoke tests |
| W20 | Observability & operations | OpenTelemetry traces, metrics, logs, dashboards, backup/restore | End-to-end run traceable; restore drill passes |
| W21 | Security hardening | Threat-model review, sandbox quotas, egress filters, secrets audit, dependency scan | No open critical finding; dangerous operations disabled by default |
| W22 | Evaluation suite | Golden tasks, regression harness, model/router comparison, cost accounting | Reproducible baseline report with failures + configuration |
| W23 | Release candidate | Installer/compose deployment, docs, onboarding, telemetry opt-in, SBOM | Clean environment deploys via documented steps |
| W24 | Public release & research package | v0.1, demo, issues/roadmap, benchmark card, limitations, technical report | Public artifacts match measured capability; limits disclosed |

## Release gates

| Gate | Must be true before proceeding |
|---|---|
| **A: vertical slice** (end W08) | User can create a task, generate a plan, approve a risk-gated action, inspect durable state/event history |
| **B: multi-agent execution** (end W12) | Research + coding workers run through stable contracts; outputs independently verified; failure ≠ false completion |
| **C: usable MVP** (end W16) | Timeline, artifacts, memory, security form one coherent experience |
| **D: compute + secure execution** (end W21) | DGX Spark optional; execution isolated; observability + incident controls live |
| **E: public-grade v0.1** (end W24) | Evaluation reproducible; docs complete; security blockers closed; claims evidence-backed |

## Do not start these too early

- 10 specialist agents before the generic agent contract + one real workflow are stable.
- Visual workflow editor before state semantics and retry behavior are settled.
- Integrating all five reference runtimes at once.
- Automatic memory promotion before provenance and correction UI work.
- Host computer access before sandbox and approval gates are tested.
- Model-routing optimization before baseline quality/cost measurements exist.
