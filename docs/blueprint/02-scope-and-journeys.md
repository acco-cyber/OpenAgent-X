# 2. Product scope, user journeys and non-goals

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 2. Adapted for OpenAgent-X.

## Primary user groups

| User | High-value jobs | Critical needs |
| --- | --- | --- |
| Researcher / PhD student | Literature review, dataset analysis, experiments, paper drafting, reproducible code and result synthesis. | Citations, reproducibility, file handling, compute selection and research-project memory. |
| Software builder | Understand a repository, create implementation plans, write code, run tests, review diffs and open pull requests. | Isolated workspaces, Git awareness, test execution, rollback and explicit publish approvals. |
| Knowledge worker | Research a topic, compare options, prepare documents and spreadsheets, manage workflows. | Browser, document tools, source tracking, templates and clear user approvals. |
| Small research team | Share project-specific agents, tools, memory and workflows. | Role-based access, team projects, auditability, cost controls and contributor governance. |

## Core journeys

**A. Research and report.** User asks for a current technical survey. Planner creates search, source review, comparison and synthesis subtasks. Research agents gather evidence; QA checks citations and dates. The system produces a sourced report and a log of sources and decisions.

**B. Build a software feature.** User selects a repository and asks for a feature. Coding agent works in a disposable project workspace, edits code and runs tests. QA inspects the diff and test results. User reviews the patch and explicitly approves any push, release or production change.

**C. Analyze a dataset.** User attaches data and asks for analysis. Data agent inspects schema and data quality, proposes a reproducible pipeline, executes in a bounded compute job, validates outputs and produces a notebook/report with artifact links.

**D. Continue a project.** User returns after days or weeks. Memory retrieves project decisions, open tasks, constraints and recent artifacts. The user can inspect and correct remembered facts before new work relies on them.

**E. Computer task with approval.** User requests an external action. Computer agent first proposes a plan and shows the target account/site and intended change. Policy service checks scope; P3/P4 actions wait for explicit approval; result and evidence are recorded.

## MVP scope: first complete loop

| MVP includes | MVP excludes |
| --- | --- |
| Three provider integrations (one cloud frontier provider, one alternative provider, one local/OpenAI-compatible endpoint). | Dozens of providers, every messaging channel, and fully autonomous background operation. |
| One central orchestrator, planner, agent registry and event ledger. | Multiple independent orchestration engines or uncontrolled self-spawning agent trees. |
| Research, coding, data and QA agent profiles. | A large catalog of narrowly specialized agents before the first workflow works. |
| A browser/search tool and one isolated coding runtime. | Unrestricted host desktop control and unattended external account actions. |
| Project memory for decisions, artifacts and task summaries. | A complex personal knowledge graph with automatic inference as a prerequisite. |
| Task trace, approval UI, verification summary and downloadable artifacts. | Enterprise multi-tenant billing, marketplace, native mobile apps and broad SaaS administration. |

## Non-functional requirements

- Task state and audit history must be durable.
- Provider outages must result in bounded retries or explicit failure, not silent degradation.
- A user can stop execution and revoke credentials or tool access.
- Project isolation is enforced in storage queries, execution mounts and tool scopes.
- The UI exposes the current task state and the reason a task is waiting or blocked.
- A run can be reproduced from its recorded configuration as far as external services allow.
