# ADR-004: Durable workflow engine

**Decision:** Use a persisted workflow engine (Temporal Python SDK for production; a simpler persisted state machine is acceptable for the earliest vertical slice).

**Reason:** Long-running work, retries, timers, cancellation and recovery are first-class workflow concerns, not ad-hoc loops.

**Consequences:** Service restarts must not lose task state; duplicate dispatch must be controlled.

**Operational impact:** Restart/resume and bounded-retry tests are release gates (H1-008, W07).
