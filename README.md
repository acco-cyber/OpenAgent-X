# OpenAgent-X

**Open, model-agnostic AI Operating System for verifiable agentic work.**
*One interface. Any model. Many specialist agents. Unified memory. Secure tools. Verifiable execution.*

OpenAgent-X is a **Universal AI Understanding Package + System Blueprint**: everything an AI (or a human team) needs to understand, build, and run a full-potential agentic system — with **lower cost and higher reliability** through capability-aware model routing, budgeted subtasks, evidence-gated verification, and deterministic orchestration.

It synthesizes the strongest ideas from five reference systems into ONE coherent, license-aware design:

| Reference | What OpenAgent-X adopts |
|---|---|
| [OpenAgent](https://github.com/the-open-agent/openagent) | Provider coverage, RAG ingestion, browser/shell/office tool patterns, MCP management, workflow builder, usage analytics |
| [MIRA](https://github.com/Vexillon-ai/MIRA) | Project/personal memory patterns, hand-editable wiki, multi-channel access, proactive briefings, skills, policy ideas |
| [OpenHands](https://github.com/OpenHands/OpenHands) | Primary coding-agent runtime adapter (Software Agent SDK / Agent Server), workspaces, events, remote execution |
| [Agent Zero](https://github.com/agent0ai/agent-zero) | Workspace/project isolation, agent profiles, plugin/skill patterns, A2A/MCP connectivity, recoverable snapshots |
| [Interpreter Workstation](https://github.com/openinterpreter/interpreter-workstation) | Computer-facing workspace, host/browser bridge separation, read-only publication, permissioned file access |

> **Architecture rule — one authority per concern.** OpenAgent-X owns canonical task state, identity, authorization, run budgets, memory policy and the audit ledger. External runtimes execute assigned work and return events/artifacts; they never independently authorize external side effects.

---

## For AI agents (start here)

If you are an AI system (Claude, GPT, Gemini, Cursor, Copilot, any agent framework):

1. Read **[`AGENTS.md`](AGENTS.md)** — the complete operating context. It is self-contained.
2. Load **[`openagent-x.manifest.json`](openagent-x.manifest.json)** — machine-readable architecture, states, permissions, contracts.
3. Validate payloads against **[`schemas/`](schemas/)** — JSON Schema for Task, AgentDefinition, AgentTask, AgentResult, Event, Memory.
4. Deep-dive **[`docs/blueprint/`](docs/blueprint/README.md)** — the full engineering blueprint (24 sections).
5. Follow **[`docs/agentic-mode/`](docs/agentic-mode/README.md)** — operating protocols to reach full agentic potential at minimal cost.

## For humans

- **Blueprint index**: [`docs/blueprint/README.md`](docs/blueprint/README.md)
- **Reference integration strategy**: [`docs/references/README.md`](docs/references/README.md)
- **Roadmap (24 weeks)**: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- **Architecture decisions**: [`docs/adr/`](docs/adr/)
- **Security**: [`SECURITY.md`](SECURITY.md) · **Contributing**: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Repository map

```
OpenAgent-X/
├── AGENTS.md                    # ★ Universal AI agent context (read first)
├── CLAUDE.md                    # Pointer for Claude-family tools
├── openagent-x.manifest.json    # Machine-readable system manifest
├── agents/                      # Agent workforce definitions (AgentDefinition)
├── skills/                      # Reusable skill library for agents
├── schemas/                     # Universal JSON Schema contracts + TS types
├── contracts/                   # TypeScript type definitions
├── docs/
│   ├── 00-ai-context.md         # How any AI bootstraps from this repo
│   ├── blueprint/               # Full engineering blueprint (24 sections)
│   ├── references/              # 5-reference analysis & integration matrix
│   ├── agentic-mode/            # Operating protocols + prompt pack
│   ├── adr/                     # Architecture decision records
│   ├── evaluation/              # Benchmark plan & v0.1 targets
│   └── operations/              # Runbooks
├── scripts/                     # Verification tooling (runs in CI)
└── .github/workflows/           # CI
```

## Status

`v0.1.0 — Blueprint & Universal Context Package. Implementation proceeds part-by-part: every part is committed, verified (CI + verify script), and pushed before the next begins.`

## Cost + reliability thesis

Agentic systems fail from **unbounded loops, unverified claims, and expensive-model-for-everything**. OpenAgent-X answers with:

- **Capability-aware routing** — cheap models for classification/extraction, reasoning models only for planning, coding profiles for code (see `docs/agentic-mode/03-cost-optimization.md`).
- **Budgeted subtasks** — every subtask carries `max_tokens`, `max_tool_calls`, wall-time and retry ceilings.
- **Evidence before claims** — a task is COMPLETED only when acceptance criteria are verified by checks/evidence, never by a confident answer.
- **Durable execution** — persisted state machine; pause/resume/cancel/recover without losing work.

## License

Apache-2.0 (see [`LICENSE`](LICENSE)). Reference repositories retain their own licenses — integration guidance in `docs/references/` (MIRA is AGPL-3.0: pattern-level inspiration only, no code reuse without legal review).
