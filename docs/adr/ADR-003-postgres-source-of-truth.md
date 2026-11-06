# ADR-003: PostgreSQL as source of truth

**Decision:** PostgreSQL stores users, projects, tasks, events, memory metadata; pgvector provides vector retrieval in the same database. Redis is cache-only; object storage holds artifacts.

**Reason:** Relational consistency, transaction boundaries, audit records and vector search in one data plane.

**Consequences:** One backup/restore story; simpler access control (project filters before retrieval).

**Operational impact:** Restore drills must verify counts/checksums/ACLs; graph DB deferred until evaluation proves value.
