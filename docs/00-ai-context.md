# 00 — AI Context: How Any AI Bootstraps From This Repository

This document is the navigation layer for AI systems. Everything else is indexed from here.

## 0. Contract of this repo with AI systems

OpenAgent-X is written so that **any AI system — regardless of vendor, framework, or size — can become fully agentic with it** by reading structured context instead of guessing. The repo therefore guarantees:

1. **A single entry point** (`AGENTS.md`) that is complete enough to operate from.
2. **Machine-readable truth** (`openagent-x.manifest.json`, `schemas/*.json`) that never contradicts the prose docs.
3. **Protocol-level discipline**: every action fits the task state machine, permission tiers, and budget ledger.
4. **Cost-aware defaults**: cheap-first routing, budgeted subtasks, evidence-gated completion.

## 1. Minimum viable context (read this much and you can work)

| File | Gives you |
|---|---|
| `AGENTS.md` §3 | The 8 prime directives |
| `AGENTS.md` §5–6 | Task states + permission tiers |
| `AGENTS.md` §7 | Agent contracts (what you emit/accept) |
| `schemas/` | Validation for every payload |
| `docs/agentic-mode/03-cost-optimization.md` | How to stay cheap and fast |

## 2. Full context (read when implementing)

1. `docs/blueprint/` — 24-section engineering blueprint: architecture, orchestration, model gateway, memory, security, data model, roadmap, evaluation.
2. `docs/references/` — what each of the 5 upstream systems contributes and what must NOT be copied (license-aware).
3. `docs/adr/` — the 10 recorded architecture decisions.
4. `docs/operations/runbooks.md` — operational procedures.

## 3. Behavioral loop for an agent working *inside* an OpenAgent-X system

```
receive AgentTask (schema-validated)
  → check permission_scope and budget before any tool call
  → plan minimally; choose cheapest sufficient model profile
  → execute with tool allowlist only; persist events around side effects
  → run deterministic checks; then independent QA for semantics
  → emit AgentResult with evidence_refs, tests, usage, limitations
  → never self-declare COMPLETED; the orchestrator verifies
```

## 4. Behavioral loop for an AI working *on* this repository

```
pick the next part (docs/ROADMAP.md order)
  → implement small and coherent
  → update schemas/docs/AGENTS.md so prose and machine truth stay aligned
  → node scripts/verify.mjs must pass
  → commit (conventional message) → push → CI green → next part
```

## 5. Anti-patterns that this repo exists to prevent

- Confident-answer completion (no evidence) — prevented by VERIFYING state + independent QA.
- Unbounded delegation loops — prevented by depth limit 2 + budgets + cycle detection.
- Secret leakage via prompts/logs/artifacts — prevented by secret broker + redaction + audit.
- Cross-project memory bleed — prevented by ACL-before-retrieval.
- Prompt-injection tool abuse — prevented by allowlists + approval gates + untrusted-data discipline.
- Cost blowups — prevented by profile ladder + token/tool budgets + escalation ladders.
