# Agent Workforce — Definitions

Specialist execution profiles for OpenAgent-X. Each file is an `AgentDefinition` validating against [`schemas/agent-definition.schema.json`](../schemas/agent-definition.schema.json). The CI verifier checks every definition declares the mandatory fields.

## Catalog

| Agent | Task types | Default profile | Permission ceiling | Runtime |
|---|---|---|---|---|
| [orchestrator](orchestrator.yaml) | planning, coordination | reasoning | P1 (own work is planning) | native |
| [research](research.yaml) | research, synthesis | balanced | P0 + web.read | native |
| [coding](coding.yaml) | coding, testing, review | coding | P2 (sandbox) | openhands |
| [data](data.yaml) | data-analysis, profiling | balanced | P2 (sandbox) | native |
| [browser](browser.yaml) | web-automation, verification | vision | P1 default; P3 via approval only | interpreter-workstation |
| [writing](writing.yaml) | documentation, reporting | balanced | P1 | native |
| [memory-curator](memory-curator.yaml) | memory-curation | fast | P1 (memory writes are candidate-only) | native |
| [qa](qa.yaml) | verification, review | balanced | P0 + test execution in sandbox | native |

## Rules

1. **Specialists, not sovereigns** — every agent runs under the same task ID, project scope, permission service, budget ledger and audit rules.
2. **Verification is in the contract** — each definition lists its `verification_policy`; QA uses independent evidence, never the producer's self-report.
3. **Start few** — a generic worker beats an unmaintainable list of narrow personas; add roles only when a real workflow demands them.
4. **Delegation depth ≤ 2** — orchestrator → specialist → at most one bounded helper.
