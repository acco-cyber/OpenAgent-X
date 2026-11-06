# ADR-007: Permission enforcement outside model prompts

**Decision:** The policy service enforces permissions at tool-invocation time. System prompts are guidance, never a security boundary.

**Reason:** Models are not trusted authorization engines; prompting cannot be a control.

**Consequences:** Default-deny checks on every call; P3+ requires hash-bound persisted approval; denials are audited and never retried.

**Operational impact:** Policy service is critical-path; permission bypass = release blocker.
