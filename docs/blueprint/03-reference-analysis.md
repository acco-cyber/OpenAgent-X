# 3. Reference repository analysis and integration strategy

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 3. Adapted for OpenAgent-X.

The five reference repositories are design inputs, not five codebases to merge. Their current project boundaries and licenses must be checked again before every integration or release. The upstream overview below reflects the repositories and official docs reviewed on 05 November 2026.

## Reference repositories

| Reference | Use in OpenAgent-X | Do not copy blindly | License note |
| --- | --- | --- | --- |
| OpenAgent | Provider coverage, RAG ingestion, browser/shell/office tool patterns, MCP management, workflow builder, usage analytics and admin observability. | Its full agent loop, provider registry and workflow engine as a second control plane. Reuse ideas or narrowly scoped code only after license and dependency review. | Repository README identifies Apache 2.0. [R1] |
| MIRA | Project/personal memory patterns, hand-editable wiki, multi-channel access, proactive briefings, skills, sandboxing and account-level policy ideas. | Its whole Rust gateway or memory/agent architecture as a core dependency. This would create a second authority for task state, permissions and memory. | AGPL-3.0; README explicitly notes network-use source obligations under section 13 for modified network services. Obtain legal review before code reuse. [R2] |
| OpenHands | Primary coding-agent runtime adapter. Use Software Agent SDK and Agent Server for agent execution, workspaces, events, tools and remote execution. | Do not treat the current OpenHands product as one repo with one responsibility. Current architecture separates Agent Canvas, SDK/Agent Server, TypeScript client and automation. [R3, R4] | The Software Agent SDK repository publishes an MIT license. Verify every package, service and asset separately; do not infer the license of all OpenHands services from the SDK license. [R5] |
| Agent Zero | Workspace, project isolation, agent profiles, plugin/skill patterns, A2A/MCP connectivity and recoverable workspace snapshots. | Do not let Agent Zero become a peer master orchestrator with independent permissions and memory. Wrap it as an optional execution adapter. | Repository README identifies MIT. Review included packages and plugins independently. [R6] |
| Interpreter Workstation | Computer-facing workspace, host/browser bridge separation, read-only publication mode, permissioned file access and user-facing agent workspace concepts. | Do not adopt host computer access as the default. Keep UI and execution endpoint boundaries explicit. | Apache 2.0; pinned dependencies and submodules retain their own licenses/notices. [R7] |

## Integration decision matrix

| Capability | Preferred approach | Priority |
| --- | --- | --- |
| LLM providers | Use a provider gateway (LiteLLM or equivalent) plus an OpenAgent-X capability registry and policy router. | P0 |
| Coding execution | Integrate OpenHands Software Agent SDK/Agent Server behind the OpenAgent-X execution adapter. | P0 |
| Research/browser tools | Implement a minimal, auditable tool set; expose tools through MCP where useful. | P0 |
| Project memory | Implement a native OpenAgent-X memory service using PostgreSQL/pgvector; borrow UX and workflow lessons from MIRA. | P1 |
| Computer workspace | Prototype Interpreter Workstation integration behind a read-only / permissioned boundary. | P1 |
| Agent Zero runtime | Add as an optional runtime after the common agent contract is stable. | P2 |
| Workflow designer | Start with a task timeline and plan editor; add drag-and-drop visual workflows only after semantics are stable. | P2 |

## The architecture rule

**ONE AUTHORITY PER CONCERN**

OpenAgent-X owns the canonical task state, user identity, authorization decision, run budget, project memory policy and audit ledger. External runtimes execute assigned work and return events/artifacts; they do not independently authorize external side effects.
