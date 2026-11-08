# Blueprint §1–3 — Product definition, scope, and reference strategy

*Faithful port of HYDRION ONE blueprint v1.0 (2026-11-05). Proposed plan, not
a claim of implemented capability.*

## 1. Executive vision and product definition

HYDRION ONE is a unified AI work environment that can reason about a user
objective, select appropriate models, coordinate specialist agents, operate
approved tools and computers, preserve project knowledge, and verify the
artifacts it produces. It should feel like a personal AI supercomputer, but
its reliability must come from explicit workflows, strong tools, measurable
capabilities and human control rather than claims that one model is
universally superhuman.

### Mission

Make advanced AI useful as a dependable computing environment: a user
describes an outcome, HYDRION ONE plans the work, routes it to the right
capabilities, executes within a bounded permission scope, checks the result
and presents evidence.

### Vision

Give individuals and research teams access to a digital workforce that can
research, reason, code, analyze data, create documents, operate software and
maintain project continuity across sessions, while keeping the user in
control of consequential actions.

### Product promise

> A single place to direct multiple AI capabilities, with transparent plans,
> visible tool actions, project memory, recoverable workspaces and
> verifiable outputs.

### What HYDRION ONE is

- A model gateway that abstracts providers and exposes capability metadata.
- A durable orchestration system that owns task state, delegation, retries,
  budgets and approvals.
- A workforce of specialist agents with explicit contracts and bounded tool
  access.
- A project-aware memory and knowledge system with provenance and correction
  controls.
- A secure execution plane for code, browser and computer tasks.
- A control interface where users can inspect, approve, pause, resume, cancel
  and audit work.

### What HYDRION ONE is not

- Not a claim that AI can autonomously do every job or replace human
  expertise.
- Not a prompt wrapper around multiple chat APIs.
- Not a free-running agent swarm with unbounded delegation or hidden tool
  access.
- Not a fork-and-merge of five upstream systems.
- Not a system that reports success merely because an LLM produced a
  confident answer.

### North-star outcome

A user can submit a moderately complex research or engineering objective and
receive a structured plan, progress visibility, controlled execution,
test/evidence results, a final deliverable and a reproducible execution
record. The same task can be resumed after interruption without losing state
or repeating unsafe side effects.

### Product principles

| Principle | Engineering consequence |
|---|---|
| Model independence | Provider-specific code is isolated behind adapters. User workflows depend on capability names, not vendor model IDs. |
| Human authority | The user owns approvals, data-sharing decisions and external side effects. |
| Durable execution | Long-running work survives process restarts and supports pause, resume, cancel and recovery. |
| Evidence before claims | Every completion claim is backed by artifacts, tool results, tests or cited sources. |
| Least privilege | Agents receive task-scoped permissions; denied actions do not become allowed through prompting. |
| Composable services | Browser, memory, code execution and channels can be replaced without rewriting the orchestrator. |
| Reproducibility | Model ID/version, prompts, tool versions, run settings, costs and outputs are recorded with each run. |

## 2. Product scope, user journeys and non-goals

### Primary user groups

| User | High-value jobs | Critical needs |
|---|---|---|
| Researcher / PhD student | Literature review, dataset analysis, experiments, paper drafting, reproducible code and result synthesis. | Citations, reproducibility, file handling, compute selection and research-project memory. |
| Software builder | Understand a repository, create implementation plans, write code, run tests, review diffs and open pull requests. | Isolated workspaces, Git awareness, test execution, rollback and explicit publish approvals. |
| Knowledge worker | Research a topic, compare options, prepare documents and spreadsheets, manage workflows. | Browser, document tools, source tracking, templates and clear user approvals. |
| Small research team | Share project-specific agents, tools, memory and workflows. | Role-based access, team projects, auditability, cost controls and contributor governance. |

### Core journeys

**A. Research and report.** User asks for a current technical survey. Planner
creates search, source review, comparison and synthesis subtasks. Research
agents gather evidence; QA checks citations and dates. The system produces a
sourced report and a log of sources and decisions.

**B. Build a software feature.** User selects a repository and asks for a
feature. Coding agent works in a disposable project workspace, edits code and
runs tests. QA inspects the diff and test results. User reviews the patch and
explicitly approves any push, release or production change.

**C. Analyze a dataset.** User attaches data and asks for analysis. Data
agent inspects schema and data quality, proposes a reproducible pipeline,
executes in a bounded compute job, validates outputs and produces a
notebook/report with artifact links.

**D. Continue a project.** User returns after days or weeks. Memory
retrieves project decisions, open tasks, constraints and recent artifacts.
The user can inspect and correct remembered facts before new work relies on
them.

**E. Computer task with approval.** User requests an external action.
Computer agent first proposes a plan and shows the target account/site and
intended change. Policy service checks scope; P3/P4 actions wait for explicit
approval; result and evidence are recorded.

### MVP scope: first complete loop

| MVP includes | MVP excludes |
|---|---|
| Three provider integrations (one cloud frontier provider, one alternative provider, one local/OpenAI-compatible endpoint). | Dozens of providers, every messaging channel, and fully autonomous background operation. |
| One central orchestrator, planner, agent registry and event ledger. | Multiple independent orchestration engines or uncontrolled self-spawning agent trees. |
| Research, coding, data and QA agent profiles. | A large catalog of narrowly specialized agents before the first workflow works. |
| A browser/search tool and one isolated coding runtime. | Unrestricted host desktop control and unattended external account actions. |
| Project memory for decisions, artifacts and task summaries. | A complex personal knowledge graph with automatic inference as a prerequisite. |
| Task trace, approval UI, verification summary and downloadable artifacts. | Enterprise multi-tenant billing, marketplace, native mobile apps and broad SaaS administration. |

### Non-functional requirements

- Task state and audit history must be durable.
- Provider outages must result in bounded retries or explicit failure, not
  silent degradation.
- A user can stop execution and revoke credentials or tool access.
- Project isolation is enforced in storage queries, execution mounts and tool
  scopes.
- The UI exposes the current task state and the reason a task is waiting or
  blocked.
- A run can be reproduced from its recorded configuration as far as external
  services allow.

## 3. Reference repository analysis and integration strategy

The five reference repositories are design inputs, not five codebases to
merge. Their current project boundaries and licenses must be checked again
before every integration or release. The upstream overview below reflects the
repositories and official docs reviewed on 05 November 2026.

| Reference | Use in HYDRION ONE | Do not copy blindly | License note |
|---|---|---|---|
| OpenAgent | Provider coverage, RAG ingestion, browser/shell/office tool patterns, MCP management, workflow builder, usage analytics and admin observability. | Its full agent loop, provider registry and workflow engine as a second control plane. Reuse ideas or narrowly scoped code only after license and dependency review. | Repository README identifies Apache 2.0. [R1] |
| MIRA | Project/personal memory patterns, hand-editable wiki, multi-channel access, proactive briefings, skills, sandboxing and account-level policy ideas. | Its whole Rust gateway or memory/agent architecture as a core dependency. This would create a second authority for task state, permissions and memory. | AGPL-3.0; README explicitly notes network-use source obligations under section 13 for modified network services. Obtain legal review before code reuse. [R2] |
| OpenHands | Primary coding-agent runtime adapter. Use Software Agent SDK and Agent Server for agent execution, workspaces, events, tools and remote execution. | Do not treat the current OpenHands product as one repo with one responsibility. Current architecture separates Agent Canvas, SDK/Agent Server, TypeScript client and automation. [R3, R4] | The Software Agent SDK repository publishes an MIT license. Verify every package, service and asset separately; do not infer the license of all OpenHands services from the SDK license. [R5] |
| Agent Zero | Workspace, project isolation, agent profiles, plugin/skill patterns, A2A/MCP connectivity and recoverable workspace snapshots. | Do not let Agent Zero become a peer master orchestrator with independent permissions and memory. Wrap it as an optional execution adapter. | Repository README identifies MIT. Review included packages and plugins independently. [R6] |
| Interpreter Workstation | Computer-facing workspace, host/browser bridge separation, read-only publication mode, permissioned file access and user-facing agent workspace concepts. | Do not adopt host computer access as the default. Keep UI and execution endpoint boundaries explicit. | Apache 2.0; pinned dependencies and submodules retain their own licenses/notices. [R7] |

### Integration decision matrix

| Capability | Preferred approach | Priority |
|---|---|---|
| LLM providers | Use a provider gateway (LiteLLM or equivalent) plus a HYDRION capability registry and policy router. | P0 |
| Coding execution | Integrate OpenHands Software Agent SDK/Agent Server behind the HYDRION execution adapter. | P0 |
| Research/browser tools | Implement a minimal, auditable tool set; expose tools through MCP where useful. | P0 |
| Project memory | Implement a native HYDRION memory service using PostgreSQL/pgvector; borrow UX and workflow lessons from MIRA. | P1 |
| Computer workspace | Prototype Interpreter Workstation integration behind a read-only / permissioned boundary. | P1 |
| Agent Zero runtime | Add as an optional runtime after the common agent contract is stable. | P2 |
| Workflow designer | Start with a task timeline and plan editor; add drag-and-drop visual workflows only after semantics are stable. | P2 |

### The architecture rule

> **ONE AUTHORITY PER CONCERN.** HYDRION owns the canonical task state, user
> identity, authorization decision, run budget, project memory policy and
> audit ledger. External runtimes execute assigned work and return
> events/artifacts; they do not independently authorize external side effects.
