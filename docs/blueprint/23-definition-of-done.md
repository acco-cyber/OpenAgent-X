# 23. Definition of done and operating procedures

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 23. Adapted for OpenAgent-X.

## Definition of done for any feature

- The feature has a documented user outcome and acceptance criteria.
- Public/internal API schemas and versioning impact are reviewed.
- Permission scope and threat surface are documented.
- Unit, integration and negative tests exist.
- Errors, timeouts, retries and cancellation behavior are handled.
- Logs and traces include correlation metadata and redact secrets.
- UI explains success, failure, waiting and recovery states.
- Docs and example configuration are updated.
- License/dependency changes are reviewed.
- The feature can be disabled safely by a feature flag or configuration.

## Operational runbooks required before v0.1

| Runbook | Minimum procedure |
|---------|-------------------|
| Provider outage | Detect unhealthy route, stop unsafe retries, select capability-compatible fallback, notify user if degraded, reconcile cost/partial output. |
| Task stuck | Inspect workflow state and heartbeat, determine whether activity is live, retryable or needs user input; never reset state manually without event record. |
| Agent runaway | Cancel workflow, revoke task token, stop runtime/container, preserve trace and workspace snapshot, classify cause. |
| Secret exposure | Revoke credential immediately, disable tool/provider, preserve relevant logs, assess data exposure, notify affected owner. |
| Sandbox compromise | Isolate worker host, disable egress, snapshot evidence, rotate secrets, rebuild from trusted image. |
| Database or object store restore | Restore to isolated environment, verify counts/checksums/ACLs, run task replay tests and document recovery point/time. |
| DGX Spark unavailable | Fail over to allowed cloud provider or queue task; never silently violate local-only privacy requirement. |
| Failed release | Disable feature flag or roll back deployment; preserve migrations compatibility and release artifacts. |

## Minimum dashboards

- Tasks created/completed/failed/cancelled by project and task type.
- Queue depth, workflow age, blocked tasks and worker saturation.
- Model request volume, p50/p95 latency, errors, fallback rate and cost.
- Tool invocation success/failure/denial and approval wait time.
- Sandbox start/stop time, CPU/RAM use and cleanup failures.
- Memory retrieval latency, precision evaluation and ACL denial counts.
- Security alerts, rate limits and unusual external egress.

## SLOs to define after baseline

Do not promise numeric production SLOs until a stable baseline exists. Instrument availability, task-start latency, API response latency, workflow recovery, artifact availability and approval delivery. Set initial internal objectives from at least two weeks of real workload observations, then publish them with the scope and measurement method.
