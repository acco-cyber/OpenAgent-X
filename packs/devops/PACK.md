# DevOps knowledge

## Change discipline

- Every change ships through review + CI; no direct pushes to shared branches.
- Infrastructure changes are code (IaC), reviewed like application code.
- One change per deploy — bisectability is worth more than speed.
- Feature flags over long-lived branches; dark-launch before enabling.

## CI/CD essentials

- Pipeline stages: lint → build → test → security scan → deploy; fail fast and visibly.
- Builds must be reproducible: pinned dependencies, no floating tags in Dockerfiles.
- Secrets live in the platform's secret store, referenced — never inlined, never echoed into logs.
- Deploy artifact is built once and promoted (same artifact to staging and prod).

## Production readiness checklist

- Health endpoints (liveness vs readiness) and graceful shutdown.
- Structured logs with request/correlation IDs; no PII or secrets in logs.
- Metrics on the four golden signals: latency, traffic, errors, saturation.
- Backups exist, are scheduled, and **restores have been tested**.

## Incident response (the loop to memorize)

1. Stabilize first (rollback, flag off, scale up) — debugging comes after mitigation.
2. Communicate: what is broken, what users see, what happens next.
3. Investigate with the timeline of changes; the newest deploy is suspect #1.
4. Blameless postmortem: contributing factors + concrete follow-ups with owners.

## Rollback discipline

- Rollback must be one command, rehearsed, and faster than fixing forward.
- Migrations are expand/contract: ship additive schema first, remove later.
- Know your data path: schema rollback without data rollback is often worse than forward-fix.

## Agent-specific pitfalls

- Never run destructive commands (drop, rm -rf, force-push) without explicit human approval.
- Quote exact commands + exit codes as evidence for every claim about system state.
- When probes fail, distinguish "app broken" from "probe misconfigured" before acting.
