# Blueprint §18–24 — Build sequence, evaluation, research, release, risk, done, appendices

*Faithful port of HYDRION ONE blueprint v1.0 (2026-11-05). Proposed plan, not
a claim of implemented capability.*

## 18. Detailed build sequence and acceptance gates

### First 10 engineering tickets

**H1-001: Create repository and CI.**
Files: README.md, pyproject.toml, package.json, .github/workflows/ci.yml,
apps/web, services/api, docs/adr.
**Acceptance:** fresh clone installs; formatting, lint and basic tests run;
secret scanning enabled.

**H1-002: Define shared identifiers and schemas.**
Files: packages/contracts/task.py, agent.py, event.py, artifact.py.
**Acceptance:** Pydantic models validate; JSON schema is exported; schema
tests cover invalid payloads.

**H1-003: Create database migrations.**
Tables: users, projects, project_members, tasks, workflow_events, artifacts.
**Acceptance:** migrations apply and rollback in test DB; tenant/project
boundary tests pass.

**H1-004: Implement task API.**
Endpoints: POST /tasks, GET /tasks/{id}, GET /tasks/{id}/events,
POST /tasks/{id}/cancel.
**Acceptance:** authenticated owner can create/read/cancel task; unauthorized
user receives denial.

**H1-005: Implement provider adapter.**
Provider interface: complete, stream, health, usage metadata, structured
output.
**Acceptance:** fake provider tests plus 3 real provider smoke tests; secrets
never appear in logs.

**H1-006: Build model registry.**
Files: services/model_gateway/registry.py, capabilities.py, routing.py.
**Acceptance:** capability filter excludes incompatible model; selected model
and reason are recorded.

**H1-007: Planner schema and validator.**
Files: services/orchestrator/planner.py, plan_schema.json, plan_validator.py.
**Acceptance:** invalid dependency graph rejected; budget and permission
fields are mandatory.

**H1-008: Durable workflow skeleton.**
Files: services/orchestrator/workflows/task_workflow.py, activities.py,
worker.py.
**Acceptance:** restart/resume and bounded retry tests pass.

**H1-009: Policy and approval service.**
Files: security/policy/decision.py, approvals.py, tests.
**Acceptance:** P3 invocation blocked until exact action-hash approval is
valid.

**H1-010: First vertical slice.**
Flow: user request -> plan -> approve -> mock tool -> verify -> artifact ->
completed.
**Acceptance:** end-to-end test checks UI/API, state transitions, event trail
and downloadable artifact.

### Do not start these too early

- Do not create 10 specialist agents before the generic agent contract and
  one real workflow are stable.
- Do not build a visual workflow editor before state semantics and retry
  behavior are settled.
- Do not integrate all five reference runtimes at once.
- Do not implement automatic memory promotion before provenance and
  correction UI work.
- Do not expose host computer access before sandbox and approval gates are
  tested.
- Do not optimize model routing before baseline quality/cost measurements
  exist.

### Day-one engineering checklist

- Create the GitHub repository with a clear README, license decision, issue
  templates and security policy.
- Create architecture/decisions.md and record the first ADRs listed in
  Section 4.
- Choose Python and TypeScript versions based on the deployment environment
  and pin them.
- Create a local compose stack for PostgreSQL, Redis and object storage.
- Build health/readiness endpoints and structured logs.
- Add an integration-test environment using fake provider responses.
- Create one sample project and one scripted end-to-end task.

## 19. Evaluation, benchmarking and reliability targets

A serious AI operating system needs an evaluation system that measures the
complete agent workflow, not only language model benchmark scores. Benchmarks
are selected by capability; none of the proposed targets below is a measured
result. Publish actual runs with model versions, runtime, hardware, task
setup, cost, failures and confidence intervals where applicable.

### Evaluation layers

| Layer | What to measure | Example evidence |
|---|---|---|
| Model | Capability, task accuracy, structured-output validity, tool-call correctness, latency and cost. | Provider-specific task sets; schema-validation rate; p50/p95 latency. |
| Agent | Subtask completion, tool precision, recovery rate, instruction adherence and artifact quality. | Golden agent tasks and independent grading rubric. |
| Orchestrator | Plan validity, dependency correctness, state invariants, cancellation and recovery. | State-machine tests, replay tests, fault injection. |
| Tools / runtime | Success rate, timeout behavior, sandbox escape attempts, artifact integrity. | Tool contract suite, adversarial security suite, runtime tests. |
| Memory | Retrieval precision/recall, provenance correctness, stale-memory handling and deletion. | Curated query/fact set and access-isolation tests. |
| End-to-end product | Task success, time-to-completion, user intervention, cost, safety violations and satisfaction. | Held-out workflows with documented scoring criteria. |

### Relevant external benchmark families

| Benchmark | What it informs | Use caution |
|---|---|---|
| SWE-bench Verified | Real repository issue resolution and code change capability. | Environment, harness and model agent configuration strongly affect results. [R16] |
| GAIA | General assistant tasks that require tool use and multi-step reasoning. | Do not equate leaderboard score with product safety or broad autonomy. [R17] |
| WebArena | Browser-based web task completion. | Website state and browser automation setup affect reproducibility. [R18] |
| OSWorld | Computer-use tasks in real applications and operating systems. | High execution complexity; isolate the environment and report resets/failures. [R19] |
| Terminal-Bench | Terminal and coding agent performance. | Record runtime, package cache, timeouts and agent harness. [R20] |
| BrowseComp | Web research and information retrieval under difficult conditions. | Document source availability and citation correctness separately. [R21] |

### Internal benchmark suite

- **Planner-100**: 100 hand-authored objectives with expected decomposition,
  dependencies and acceptance criteria.
- **Tool-50**: 50 read/write tool cases covering valid, invalid, denied,
  timeout and adversarial inputs.
- **Recovery-30**: process crash, provider outage, rate limit, workspace
  failure and cancellation scenarios.
- **Memory-100**: 100 queries with expected source IDs, ACL constraints and
  stale/conflicting facts.
- **End-to-end-25**: 25 representative workflows across research, coding,
  data and document generation.
- **Security-red-team**: prompt injection, secret exfiltration, cross-project
  access and permission-bypass attempts.

### Proposed v0.1 targets (not achieved results)

| Metric | Proposed target | Measurement definition |
|---|---|---|
| Provider adapters | 3 reliable providers at launch; 10+ over time. | Adapters pass normalized contract tests, including streaming and errors. |
| Agent profiles | 4 initial profiles; 10 core profiles after stabilization. | Each has versioned contract, tests and tool allowlist. |
| Task traceability | 100% of completed tasks have event trail and artifact provenance. | No orphan task completion or unlinked artifacts in release tests. |
| Controlled tool success | >=95% in the curated non-adversarial tool suite. | Successful expected outcome / valid authorized test invocation. |
| Permission bypass | 0 critical bypasses in release-blocking security suite. | Any unauthorized P3/P4 action is a release blocker. |
| Recovery | >=90% of pre-defined recoverable fault cases recover or fail safely. | No silent data corruption or duplicate external side effects. |
| Memory precision@5 | >=85% on curated project retrieval queries. | Relevant authorized sources in top five / all returned top-five sources; define scoring rubric before run. |
| Benchmark reproducibility | 100% of public runs include config, model, runtime, hardware and raw result artifact. | Required run metadata is present and immutable. |

### Experiment reporting template

- Hypothesis and primary metric, registered before running the experiment.
- Dataset, task selection, version, licenses and split strategy.
- Model/provider/version, prompts, routing policy and tool versions.
- Hardware, driver/runtime versions, container hashes and context settings.
- Success/failure counts, confidence intervals where appropriate, cost and
  latency.
- Ablations: single agent vs multi-agent, model routing vs fixed model,
  verifier vs no verifier, memory vs no memory.
- Error taxonomy and representative failure cases.
- Limitations and any manual intervention.

## 20. Research contributions and paper strategy

HYDRION ONE can become more than a product demo if the team isolates a
research question and produces reproducible evidence. The strongest
publishable direction is not simply "an AI with many agents." A more
defensible contribution is a verifiable, resource-aware orchestration
framework that coordinates heterogeneous models and execution tools under
explicit constraints.

### Candidate contribution A: capability-aware routing under task constraints

Research question: can task-conditioned routing over heterogeneous model
deployments reduce cost and latency while preserving end-to-end task success
and policy compliance compared with fixed-model and cost-only baselines?

- Formalize task requirements as a capability vector and hard policy
  constraints.
- Compare fixed frontier model, cheapest eligible model, latency-first and
  HYDRION router.
- Measure success, cost, latency, schema validity, tool reliability and
  fallback frequency.
- Ablate benchmark-informed quality priors, runtime health and data-policy
  filtering.

### Candidate contribution B: evidence-gated multi-agent verification

Research question: when does independent verification improve task
reliability, and what additional cost does it introduce?

- Compare single-agent completion, producer plus same-model critique, and
  independent verifier.
- Use objective task suites with deterministic checks wherever possible.
- Measure false completion rate, correction rate, time, tokens and user
  intervention.
- Analyze correlated failures between producing and verifying models.

### Candidate contribution C: resource-aware orchestration

Research question: can the orchestrator choose between local inference,
cloud inference and isolated execution workers based on quality, privacy,
cost and resource availability?

- Define resource constraints and a scheduling objective.
- Compare cloud-only, local-only, static hybrid and adaptive hybrid.
- Record DGX Spark utilization, memory, queue time, quality and end-to-end
  cost.
- Evaluate graceful degradation when local compute is overloaded or
  unavailable.

### Candidate contribution D: project memory with provenance and access isolation

Research question: does provenance-aware project memory improve long-horizon
task continuity without increasing cross-project leakage or stale-memory
errors?

- Compare no memory, conversation summary, vector retrieval and
  provenance-aware memory.
- Measure retrieval accuracy, task success, stale fact usage, ACL correctness
  and deletion completeness.
- Include contradictory decisions and user corrections in the benchmark.

### Suggested paper structure

1. Introduction and problem formulation.
2. Related work: model routing, tool-using agents, multi-agent orchestration,
   long-running workflow engines, memory and agent evaluation.
3. HYDRION architecture and formal task/permission model.
4. Algorithms: capability routing, planning/delegation and verification.
5. Experimental setup: datasets, task suites, models, runtimes and compute.
6. Results: end-to-end success, cost, latency, reliability and safety.
7. Ablation and failure analysis.
8. Limitations, threat model and reproducibility statement.

### Claims discipline

> **RESEARCH INTEGRITY.** Do not describe the system as state-of-the-art,
> superhuman or universally autonomous without benchmark evidence.
> Distinguish implemented features from planned ones, and internal targets
> from measured results. A transparent failure analysis is more credible than
> an inflated leaderboard claim.

## 21. Release, open-source governance and GitHub growth

### Public repository positioning

Recommended positioning: "HYDRION ONE is an open-source, model-agnostic AI
operating system for verifiable agentic work." The README should immediately
show what works today, a 60-90 second demo, architecture, quick start,
security posture, benchmark status and roadmap.

### Minimum public repository contents

- README.md with one-sentence value proposition, GIF/video, architecture
  diagram and tested installation path.
- LICENSE selected after contribution and dependency review; do not choose a
  license only for marketing.
- SECURITY.md with private vulnerability reporting instructions.
- CONTRIBUTING.md and CODE_OF_CONDUCT.md.
- docs/architecture.md, docs/security.md, docs/operations.md and
  docs/development.md.
- Example projects and reproducible sample tasks.
- Evaluation report with exact versions and known failures.
- Issue templates: bug, feature, integration request, security issue (private
  channel), evaluation result.
- Release notes, checksums, SBOM and container image provenance.

### GitHub growth strategy

| Mechanism | Execution | Success signal |
|---|---|---|
| Show, do not claim | Publish short demonstrations of a complete workflow with visible tool trace and verified artifacts. | Users can reproduce the demo. |
| Research artifacts | Release benchmark suite, eval harness, task traces with sensitive data removed and ablation scripts. | External researchers run and cite the evaluation. |
| Integration ecosystem | Document provider, MCP and agent-runtime adapters with clear contribution guide. | Independent integration PRs and forks. |
| Build-in-public | Weekly changelog, roadmap updates, design decisions and failure writeups. | Returning contributors and meaningful discussions. |
| Onboarding | One-command local demo with mock provider and optional real API configuration. | First successful task and low setup friction. |
| Community | Respond to issues, label good first issues, publish contributor docs and keep milestones realistic. | Issue resolution time and contributor retention. |

### Launch sequence

1. Private alpha: founder and trusted collaborators run workflows and
   security tests.
2. Public technical preview: publish source, architecture and known
   limitations; default demo uses mock or safe tools.
3. v0.1 release: include the first end-to-end workflow, stable install,
   measured evaluation and documented security defaults.
4. v0.2: add memory quality improvements, more provider/runtime adapters and
   better local inference.
5. v1.0 only after stability, upgrade compatibility, backup/restore and clear
   support boundaries are demonstrated.

### Open-source licensing workflow

- Choose a project license after reviewing desired reuse, contribution model
  and dependency compatibility.
- Maintain THIRD_PARTY_NOTICES and machine-readable SBOM.
- For every upstream integration, record repository, version/commit, license,
  files copied, modifications and obligations.
- Review AGPL implications for MIRA before copying, modifying or distributing
  code or operating a modified network service.
- Check pinned submodules and transitive packages for Interpreter
  Workstation.
- Check individual OpenHands repositories/packages rather than assuming one
  license applies to all.
- Do not reuse names, logos or trademarks in a way that implies endorsement.
- Have qualified legal counsel review any commercial distribution or code
  derived from copyleft projects.

## 22. Risk register and mitigation plan

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Scope explosion | High | Critical | Freeze MVP to one complete workflow; make all nonessential integrations P2/P3. |
| R2 | Agent loops create false success | High | Critical | Deterministic acceptance checks, independent verifier, terminal-state invariants. |
| R3 | Prompt injection leads to unsafe tool use | High | Critical | Tool allowlists, data/instruction separation, approvals, red-team tests. |
| R4 | Runtime grants host-level access | Medium | Critical | Dedicated sandbox; no broad mounts; disable host access in MVP. |
| R5 | Model provider outages or drift | High | High | Fallbacks that preserve capability and data constraints; versioned evaluation. |
| R6 | Model routing selects incompatible models | Medium | High | Hard capability filters and contract tests. |
| R7 | Memory leaks across projects | Medium | Critical | ACL filtering before retrieval, DB tests and artifact isolation. |
| R8 | AGPL or dependency license conflict | Medium | High | SBOM, provenance, isolated adapters, counsel review. |
| R9 | DGX Spark software/runtime mismatch | Medium | Medium | Validate driver/runtime support; retain cloud API path; benchmark actual compatibility. |
| R10 | High inference cost | High | High | Per-task budgets, routing profiles, caching where safe and usage reporting. |
| R11 | Low reproducibility | Medium | High | Immutable run config, pinned containers, model/version metadata and artifact hashes. |
| R12 | Solo-developer delivery overload | High | High | Build in milestones, use managed components, delay desktop and marketplace work. |
| R13 | Public claims exceed evidence | Medium | High | Publish a benchmark card, limitations and measured-only release claims. |
| R14 | Operational complexity exceeds value | Medium | High | Avoid premature microservices, Kubernetes, NATS, graph DB and multiple runtimes. |

### Risk review cadence

Review the risk register weekly. Any critical security finding blocks
release. Any high-impact reliability issue must have an owner, mitigation and
test. Reassess risk after introducing a new runtime, tool class, provider,
data type or permission level.

## 23. Definition of done and operating procedures

### Definition of done for any feature

- The feature has a documented user outcome and acceptance criteria.
- Public/internal API schemas and versioning impact are reviewed.
- Permission scope and threat surface are documented.
- Unit, integration and negative tests exist.
- Errors, timeouts, retries and cancellation behavior are handled.
- Logs and traces include correlation metadata and redact secrets.
- UI explains success, failure, waiting and recovery states.
- Docs and example configuration are updated.
- License/dependency changes are reviewed.
- The feature can be disabled safely by a feature flag or configuration.

### Operational runbooks required before v0.1

| Runbook | Minimum procedure |
|---|---|
| Provider outage | Detect unhealthy route, stop unsafe retries, select capability-compatible fallback, notify user if degraded, reconcile cost/partial output. |
| Task stuck | Inspect workflow state and heartbeat, determine whether activity is live, retryable or needs user input; never reset state manually without event record. |
| Agent runaway | Cancel workflow, revoke task token, stop runtime/container, preserve trace and workspace snapshot, classify cause. |
| Secret exposure | Revoke credential immediately, disable tool/provider, preserve relevant logs, assess data exposure, notify affected owner. |
| Sandbox compromise | Isolate worker host, disable egress, snapshot evidence, rotate secrets, rebuild from trusted image. |
| Database or object store restore | Restore to isolated environment, verify counts/checksums/ACLs, run task replay tests and document recovery point/time. |
| DGX Spark unavailable | Fail over to allowed cloud provider or queue task; never silently violate local-only privacy requirement. |
| Failed release | Disable feature flag or roll back deployment; preserve migrations compatibility and release artifacts. |

### Minimum dashboards

- Tasks created/completed/failed/cancelled by project and task type.
- Queue depth, workflow age, blocked tasks and worker saturation.
- Model request volume, p50/p95 latency, errors, fallback rate and cost.
- Tool invocation success/failure/denial and approval wait time.
- Sandbox start/stop time, CPU/RAM use and cleanup failures.
- Memory retrieval latency, precision evaluation and ACL denial counts.
- Security alerts, rate limits and unusual external egress.

### SLOs to define after baseline

Do not promise numeric production SLOs until a stable baseline exists.
Instrument availability, task-start latency, API response latency, workflow
recovery, artifact availability and approval delivery. Set initial internal
objectives from at least two weeks of real workload observations, then
publish them with the scope and measurement method.

## 24. Technical appendices and reference links

### Appendix A: minimal environment configuration

```text
# Example names only. Store actual secret values in a secrets manager.
APP_ENV=development
API_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql://hydrion:***@localhost:5432/hydrion
REDIS_URL=redis://localhost:6379/0
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_BUCKET=hydrion-artifacts
OIDC_ISSUER_URL=
OIDC_CLIENT_ID=
SECRET_MANAGER_BACKEND=local-dev-only
MODEL_GATEWAY_URL=http://localhost:4000
TEMPORAL_ADDRESS=localhost:7233
EXECUTION_BACKEND=docker
DEFAULT_TASK_BUDGET_USD=5
DEFAULT_MAX_TOOL_CALLS=30
ALLOW_HOST_COMPUTER_ACCESS=false
ALLOW_EXTERNAL_WRITES=false
```

The local-development secret backend must be clearly marked and must never be
used in a production deployment. Commit only an .env.example with blank
placeholders.

### Appendix B: initial acceptance suite

| Test ID | Scenario | Expected result |
|---|---|---|
| T-001 | Create task with valid objective. | Task ID returned; CREATED event persisted. |
| T-002 | Planner emits malformed plan. | Plan rejected; no agent dispatched. |
| T-003 | Agent requests tool outside allowlist. | Invocation denied by policy service and audited. |
| T-004 | P3 external action without approval. | Blocked; no network side effect occurs. |
| T-005 | P3 action approved for a different payload hash. | Approval rejected as non-matching. |
| T-006 | Provider timeout. | Bounded retry/fallback; failure reason visible. |
| T-007 | Worker crashes after event persistence. | Workflow resumes or safely reconciles without duplicate side effect. |
| T-008 | Project A user queries Project B memory. | No Project B content returned. |
| T-009 | Verifier finds failed acceptance criterion. | Task does not transition to COMPLETED. |
| T-010 | User cancels during code execution. | Cancellation propagates; workspace cleanup and audit event occur. |
| T-011 | Artifact is changed after completion. | Checksum mismatch detected. |
| T-012 | DGX Spark endpoint becomes unavailable. | Allowed fallback or waiting state; local-only task remains blocked. |

### Appendix C: required architecture decision records

- ADR-001: canonical orchestration and event ownership.
- ADR-002: model gateway and routing ownership.
- ADR-003: authorization, approval token and risk taxonomy.
- ADR-004: execution isolation and workspace lifecycle.
- ADR-005: PostgreSQL/pgvector and memory retention.
- ADR-006: external runtime adapters and version compatibility.
- ADR-007: source/license policy and third-party notices.
- ADR-008: deployment boundaries and DGX Spark networking.
- ADR-009: model/data privacy classes and provider eligibility.
- ADR-010: benchmark protocol and public reporting requirements.

### Appendix D: key external references

The following primary project and documentation pages were reviewed for this
blueprint. GitHub default branches and documentation evolve; pin exact
versions/commits and re-check license and deployment instructions before
implementation or release.

- [R1] OpenAgent repository README and feature overview —
  https://github.com/the-open-agent/openagent
- [R2] MIRA repository README, architecture and AGPL-3.0 notice —
  https://github.com/Vexillon-ai/MIRA
- [R3] OpenHands Agent Canvas repository and current component boundaries —
  https://github.com/OpenHands/OpenHands
- [R4] OpenHands Software Agent SDK and Agent Server documentation —
  https://github.com/OpenHands/software-agent-sdk
- [R5] OpenHands Software Agent SDK MIT license file —
  https://github.com/OpenHands/software-agent-sdk/blob/main/LICENSE
- [R6] Agent Zero repository, project docs and MIT license statement —
  https://github.com/agent0ai/agent-zero
- [R7] Interpreter Workstation repository, architecture and Apache 2.0
  license note —
  https://github.com/openinterpreter/interpreter-workstation
- [R8] LiteLLM routing and load-balancing documentation —
  https://docs.litellm.ai/docs/routing
- [R9] Model Context Protocol specification —
  https://modelcontextprotocol.io/specification/
- [R10] MCP authorization specification (2025-11-25) —
  https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- [R11] Agent2Agent Protocol specification —
  https://a2a-protocol.org/v1.0.1/specification/
- [R12] Temporal Python SDK developer guide — https://docs.temporal.io/develop/python
- [R13] OpenTelemetry Python documentation — https://opentelemetry.io/docs/languages/python/
- [R14] NVIDIA DGX Spark official specifications —
  https://www.nvidia.com/en-us/products/workstations/dgx-spark/
- [R15] vLLM OpenAI-compatible server and API-key security caveat —
  https://docs.vllm.ai/en/latest/serving/openai_compatible_server/
- [R16] SWE-bench — https://www.swebench.com/
- [R17] GAIA benchmark — https://huggingface.co/gaia-benchmark
- [R18] WebArena — https://webarena.dev/
- [R19] OSWorld — https://os-world.github.io/
- [R20] Terminal-Bench — https://terminal-bench.com/
- [R21] BrowseComp — https://browsecomp.github.io/

### Final recommendation (verbatim)

> **BUILD THIS FIRST.** Ship a single safe, durable and verifiable workflow
> before expanding the system: submit an objective -> create a plan -> approve
> it -> delegate research or coding -> execute through one isolated runtime ->
> verify evidence/tests -> generate artifacts -> persist the complete trace.
> That vertical slice is the foundation for every later capability.

*End of blueprint port. Document status: proposed plan. Implementation
status and benchmark outcomes must be updated as evidence becomes available.*
