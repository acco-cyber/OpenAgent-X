# ADR-006: One execution runtime initially

**Decision:** OpenHands Software Agent SDK/Agent Server is the first and only coding runtime until the MVP is stable. Agent Zero (P2) and Interpreter Workstation (P1 prototype) come later behind adapters.

**Reason:** Keep attack surface and operational complexity manageable.

**Consequences:** Multi-runtime orchestration is explicitly out of scope for MVP.

**Operational impact:** Adapter interface must be kept honest so later runtimes plug in without planner changes.
