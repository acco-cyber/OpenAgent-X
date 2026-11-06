# Architecture Decision Records

Ten recorded decisions that define OpenAgent-X's shape. Status: **Accepted** (from blueprint); revisit only with a written supersession.

| ADR | Decision | File |
|---|---|---|
| 001 | Single canonical orchestrator + append-only event ownership | [ADR-001](ADR-001-canonical-orchestration.md) |
| 002 | Agent contract independent of runtime | [ADR-002](ADR-002-agent-contract.md) |
| 003 | PostgreSQL as source of truth (+ pgvector) | [ADR-003](ADR-003-postgres-source-of-truth.md) |
| 004 | Durable workflow engine (Temporal after MVP skeleton) | [ADR-004](ADR-004-durable-workflows.md) |
| 005 | MCP for tools, A2A for external agents | [ADR-005](ADR-005-mcp-a2a-boundaries.md) |
| 006 | One execution runtime initially (OpenHands) | [ADR-006](ADR-006-one-runtime-first.md) |
| 007 | Permission enforcement outside model prompts | [ADR-007](ADR-007-policy-outside-prompts.md) |
| 008 | Execution isolation & workspace lifecycle | [ADR-008](ADR-008-execution-isolation.md) |
| 009 | Source/license policy & third-party notices | [ADR-009](ADR-009-license-policy.md) |
| 010 | Benchmark protocol & public reporting requirements | [ADR-010](ADR-010-benchmark-protocol.md) |

## ADR format

Each ADR: **Decision** (what), **Reason** (why), **Consequences** (what it costs/implies), **Operational impact** (failure modes to plan for). New ADRs follow the same format and get sequential numbers.
