# 22. Risk register and mitigation plan

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 22. Adapted for OpenAgent-X.

## Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | Scope explosion | High | Critical | Freeze MVP to one complete workflow; make all nonessential integrations P2/P3. |
| R2 | Agent loops create false success | High | Critical | Deterministic acceptance checks, independent verifier, terminal-state invariants. |
| R3 | Prompt injection leads to unsafe tool use | High | Critical | Tool allowlists, data/instruction separation, approvals, red-team tests. |
| R4 | Runtime grants host-level access | Medium | Critical | Dedicated sandbox; no broad mounts; disable host access in MVP. |
| R5 | Model provider outages or drift | High | High | Fallbacks that preserve capability and data constraints; versioned evaluation. |
| R6 | Model routing selects incompatible models | Medium | High | Hard capability filters and contract tests. |
| R7 | Memory leaks across projects | Medium | Critical | ACL filtering before retrieval, DB tests and artifact isolation. |
| R8 | AGPL or dependency license conflict | Medium | High | SBOM, provenance, isolated adapters, counsel review. |
| R9 | DGX Spark software/runtime mismatch | Medium | Medium | Validate driver/runtime support; retain cloud API path; benchmark actual compatibility. |
| R10 | High inference cost | High | High | Per-task budgets, routing profiles, caching where safe and usage reporting. |
| R11 | Low reproducibility | Medium | High | Immutable run config, pinned containers, model/version metadata and artifact hashes. |
| R12 | Solo-developer delivery overload | High | High | Build in milestones, use managed components, delay desktop and marketplace work. |
| R13 | Public claims exceed evidence | Medium | High | Publish a benchmark card, limitations and measured-only release claims. |
| R14 | Operational complexity exceeds value | Medium | High | Avoid premature microservices, Kubernetes, NATS, graph DB and multiple runtimes. |

## Risk review cadence

Review the risk register weekly. Any critical security finding blocks release. Any high-impact reliability issue must have an owner, mitigation and test. Reassess risk after introducing a new runtime, tool class, provider, data type or permission level.
