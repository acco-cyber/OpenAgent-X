# 8. Tools, MCP, A2A and external runtimes

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 8. Adapted for OpenAgent-X.

## Tool strategy

Use a small built-in tool set for the MVP, then expose compatible integrations through MCP. MCP provides a common protocol for tool discovery and invocation, but it does not replace OpenAgent-X authorization, consent UI or runtime sandboxing. The MCP specification explicitly places important consent and trust responsibilities on implementers. [R9, R10]

## Tool family

| Tool family | First version | Later extensions |
| --- | --- | --- |
| Research | Search, fetch page, extract metadata, save source record. | Browser sessions, scholarly APIs, DOI resolution, citation graph. |
| Files | List/read/write files inside project sandbox; artifact upload/download. | Cross-format office viewers, OCR/image processing, conversion services. |
| Code | Run commands in isolated workspace, apply patch, execute tests. | Multiple runtime backends, remote build workers and GPU jobs. |
| Data | Inspect CSV/Parquet, execute bounded Python, create plots and reports. | SQL connectors, data warehouse tools and distributed compute. |
| Git | Clone, branch, diff, commit to local sandbox. | PR creation, CI monitoring and guarded merge. |
| Computer | Browser navigation and screenshots; no broad host control by default. | Permissioned desktop bridge and multi-application workflows. |
| Communication | In-app notification and task events. | Email, Slack, Telegram and other channels after identity/policy integration. |

## MCP integration rules

- Maintain an allowlisted registry of MCP servers and tools per project.
- Pin server package/version or container digest where possible.
- Validate tool input/output schemas and size limits.
- Separate read tools from write tools and define their risk class.
- Require approval for external side effects; provide deny controls in UI.
- Treat resource contents and tool results as untrusted prompt-injection surfaces.
- Record server identity, tool name, arguments (with secrets redacted), result metadata and approval ID.

## A2A and external agent interoperability

Use A2A as an optional boundary for delegating tasks to independent agent systems. Its protocol is designed for capability discovery, task collaboration and exchange across agents that may not expose their internal memory or tools. [R11] OpenAgent-X should translate an external agent into its internal AgentTask/AgentResult contract and apply the same policy, budget, timeout and verification gates.

## Runtime adapter sequence

1. OpenAgent-X validates task and permissions.
2. Adapter creates or selects an isolated runtime/workspace.
3. Adapter passes an approved task envelope and artifact references.
4. Runtime emits execution events and returns artifacts/evidence.
5. OpenAgent-X records events, checks output schemas and runs verification.
6. Adapter terminates or parks the runtime and confirms cleanup.

## OpenHands-first coding integration

Current OpenHands documentation describes a multi-repository system: the Agent Canvas frontend, the Software Agent SDK/Agent Server, a TypeScript client and an automation service have distinct responsibilities. For OpenAgent-X, start with the Python SDK / Agent Server API as an execution backend and build a thin adapter. Do not embed the entire Agent Canvas into OpenAgent-X UI unless the integration provides a clear benefit. [R3, R4]
