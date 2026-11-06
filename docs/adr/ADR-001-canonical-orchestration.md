# ADR-001: Single canonical orchestrator and event ownership

**Decision:** One orchestrator owns all task state, delegation, retries, budgets and approvals. Every transition and side effect is persisted as an append-only workflow event.

**Reason:** Divergent task state, duplicate retries and conflicting approval semantics are the primary failure modes of multi-agent systems.

**Consequences:** All agent activity flows through the orchestrator; agents cannot mutate state directly. Event ledger becomes the audit backbone.

**Operational impact:** Ledger availability is critical-path; replay is the recovery mechanism; ledger tampering protection (append-only + external sink) is mandatory.
