# Reference Integration Strategy — Five Upstream Systems

The five reference repositories are **design inputs, not codebases to merge**. OpenAgent-X is a new control plane that borrows the best patterns from each, behind clean adapters, with license awareness.

> **THE ARCHITECTURE RULE — ONE AUTHORITY PER CONCERN.** OpenAgent-X owns the canonical task state, user identity, authorization decision, run budget, project memory policy and audit ledger. External runtimes execute assigned work and return events/artifacts; they do not independently authorize external side effects.

## Integration decision matrix

| Capability | Preferred approach | Priority |
|---|---|---|
| LLM providers | Provider gateway (LiteLLM or equivalent) + OpenAgent-X capability registry and policy router | P0 |
| Coding execution | Integrate OpenHands Software Agent SDK / Agent Server behind the OpenAgent-X execution adapter | P0 |
| Research/browser tools | Minimal, auditable built-in tool set; expose tools through MCP where useful | P0 |
| Project memory | Native memory service (PostgreSQL/pgvector); borrow UX and workflow lessons from MIRA | P1 |
| Computer workspace | Prototype Interpreter Workstation integration behind read-only / permissioned boundary | P1 |
| Agent Zero runtime | Add as optional runtime after the common agent contract is stable | P2 |
| Workflow designer | Task timeline + plan editor first; drag-and-drop visual workflows only after semantics stabilize | P2 |

## Reference files

1. [OpenAgent](openagent.md) — provider coverage, RAG, tool patterns, MCP, analytics (Apache-2.0)
2. [MIRA](mira.md) — memory, wiki, skills, policy patterns (⚠ AGPL-3.0)
3. [OpenHands](openhands.md) — primary coding runtime adapter (MIT SDK; verify per package)
4. [Agent Zero](agent-zero.md) — isolation, profiles, snapshots, optional runtime (MIT)
5. [Interpreter Workstation](interpreter-workstation.md) — computer workspace, bridge separation (Apache-2.0)

## Global rules for any integration

1. Record for every upstream use: repository, version/commit, license, files/patterns copied, modifications, obligations.
2. Pin versions/container digests; re-check licenses before every release.
3. Reuse standards (MCP, A2A, OpenAI-compatible APIs) at boundaries — protocol support is not a security model.
4. One execution runtime initially; add others only when the MVP is stable.
5. No name/logo/trademark reuse implying endorsement. Legal review for any copyleft-derived distribution.
