# CLAUDE.md

**Read `AGENTS.md` first.** It is the complete, self-contained operating context for this repository. This file is a condensed pointer for Claude-family tools.

## Absolute rules (from AGENTS.md §3)

1. **Human authority** — user owns approvals and external side effects.
2. **Evidence before claims** — no completion claim without artifact/test/citation evidence.
3. **Least privilege** — task-scoped permissions; denials are never bypassed via prompting.
4. **Deterministic orchestration** — models propose; the orchestrator validates, persists, enforces.
5. **Durable execution** — persist state transitions as events; support pause/resume/cancel/recover.
6. **One authority per concern** — external runtimes execute work; they never authorize side effects.
7. **Cost discipline** — budget every subtask; escalate model tiers only when cheaper paths fail.
8. **Reproducibility** — record model/version, prompts, tool versions, costs, outputs.

## Working here

- Read order: `AGENTS.md` → `openagent-x.manifest.json` → `schemas/` → `docs/agentic-mode/` → `docs/blueprint/`.
- Validate every Task/Agent/Event/Memory payload against `schemas/*.json`.
- Follow the canonical task state machine (11 states) and permission tiers P0–P4 (default deny).
- Part-by-part rhythm: build → `node scripts/verify.mjs` → commit → push → confirm green → next part.
- Never commit secrets. Never store secrets in prompts, memory, or artifacts.

## Non-negotiables when implementing

- PostgreSQL as source of truth; append-only event ledger; idempotency keys for side effects.
- Structured outputs validated against JSON Schema before dispatch.
- Independent verifier for QA; deterministic checks first.
- MIRA is AGPL-3.0: pattern inspiration only, no code reuse.
