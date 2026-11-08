# The HYDRION ONE Blueprint — design input for OpenAgent-X

This directory is a **faithful, full port** of the *HYDRION ONE — Complete
Product, Research and Engineering Blueprint* (Hydrion AI Lab, document v1.0,
reference review 05 November 2026, 36 pages). It is stored here the way the
blueprint itself asks upstream material to be stored: as a **design input**,
not as a claim of implemented capability.

> **Status (verbatim from the blueprint):** *Proposed architecture and
> execution plan, not a claim of implemented capability.* Nothing in these
> files describes something OpenAgent-X has measured. Where OpenAgent-X has
> since turned a blueprint section into checked code, the pointer is written
> explicitly (e.g. §5 → `openagentx/lifecycle.py`). Everything else is a
> target until measured.

**Why it is here.** OpenAgent-X's own rules say upstream material is a design
input, never a fork-and-merge. The HYDRION ONE blueprint is the most complete
reference the project has for the *control-plane* concerns this repo cares
about — durable task lifecycles, permission tiers, approval semantics,
evaluation discipline, threat models and release gates. Porting it in full
(claims discipline included) makes every design conversation citable.

**Core product principle (blueprint, page 1):**

> One interface. Any model. Many specialist agents. Unified memory. Secure
> tools. Verifiable execution.

## Files

| File | Blueprint sections | Contents |
|---|---|---|
| [`01-product.md`](01-product.md) | §1–3 | Executive vision, scope, user journeys, MVP boundary, reference-repository analysis and integration strategy |
| [`02-architecture.md`](02-architecture.md) | §4–8 | Seven logical layers, orchestration engine and durable task lifecycle, model gateway and capability-aware routing, agent workforce, tools/MCP/A2A |
| [`03-platform.md`](03-platform.md) | §9–12 | Memory and knowledge, execution environments and computer use, security/permissions/threat model, data model/APIs/event contracts |
| [`04-delivery.md`](04-delivery.md) | §13–17 | UX and interface requirements, technology stack, DGX Spark compute strategy, monorepo standards, 24-week roadmap |
| [`05-evidence.md`](05-evidence.md) | §18–24 | Build sequence and acceptance gates, evaluation and reliability targets, research contributions, release/governance, risk register, definition of done, appendices |

## Document control (blueprint, page 2)

| Field | Definition |
|---|---|
| Project | HYDRION ONE, Universal AI Operating System |
| Owner | Hydrion AI Lab |
| Purpose | Convert the product thesis into an implementable architecture, roadmap, evaluation plan and release process |
| Audience | Founder, AI/ML engineers, full-stack engineers, security reviewers, research collaborators and contributors |
| Planning horizon | 24 weeks to a first public-grade release, assuming consistent engineering capacity. A planning estimate, not a delivery guarantee |
| Technical posture | API-first, model-agnostic, modular, self-hostable, human-governed and evidence-driven |
| Current state | Blueprint only. All acceptance criteria are targets until measured in the implementation |

## Decision summary (blueprint, page 2)

- **Build a new control plane.** Do not combine all five reference
  repositories into one monolith or let each runtime own its own permissions,
  memory and task lifecycle.
- **Start with one end-to-end workflow.** A user request should become a
  persisted plan, delegated work, controlled tool execution, independent
  verification and a traceable deliverable.
- **Choose one primary coding runtime first.** Use the OpenHands Software
  Agent SDK/Agent Server as the first coding execution adapter. Keep other
  runtimes behind adapters and add them only when the MVP is stable.
- **Keep orchestration deterministic.** The model proposes plans; the
  orchestrator validates, persists, schedules and enforces them.
- **Treat safety as an execution property.** Permission checks, sandbox
  boundaries, secret handling and audit events must be enforced outside model
  prompts.
- **Use DGX Spark as an inference/compute node**, not as a reason to make the
  product hardware-dependent. Cloud model APIs remain available, while local
  inference is selected when capabilities, privacy, speed and cost justify it.

## The architecture rule (blueprint, §3)

> **ONE AUTHORITY PER CONCERN.** HYDRION owns the canonical task state, user
> identity, authorization decision, run budget, project memory policy and
> audit ledger. External runtimes execute assigned work and return
> events/artifacts; they do not independently authorize external side effects.

OpenAgent-X reads this the same way it reads its own ADR-0001: one journal is
the truth, guards refuse before side effects, and the model never becomes an
authorization engine.

## Final recommendation (blueprint, §24 — verbatim)

> **BUILD THIS FIRST.** Ship a single safe, durable and verifiable workflow
> before expanding the system: submit an objective → create a plan → approve
> it → delegate research or coding → execute through one isolated runtime →
> verify evidence/tests → generate artifacts → persist the complete trace.
> That vertical slice is the foundation for every later capability.

## How OpenAgent-X consumes the blueprint

| Blueprint section | OpenAgent-X status |
|---|---|
| §5 durable task lifecycle | **ported to code** — [`openagentx/lifecycle.py`](../../openagentx/lifecycle.py), graded by golden task 47 (`drill lifecycle`) |
| §5 approval bound to the exact plan hash | **ported to code** — same module (`ApprovalMismatch`) |
| §5 canonical task states | **ported to code** — the eleven-state table lives in `lifecycle.TRANSITIONS`, pinned by the drill |
| §11 append-only audit, redaction at boundaries | **already built** — the journal boundary, `redact.py` (11 species), `oax audit` |
| §19 evaluation discipline | **already built** — the golden matrix, honest grading, counts that only move forward |
| Everything else | design input only — see the per-file status lines above |
