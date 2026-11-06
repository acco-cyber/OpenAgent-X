# Operational Runbooks

Required before v0.1 (blueprint §23). Each runbook: detect → contain → recover → record.

| Runbook | Minimum procedure |
|---|---|
| **Provider outage** | Detect unhealthy route → stop unsafe retries → select capability-compatible fallback → notify user if degraded → reconcile cost/partial output |
| **Task stuck** | Inspect workflow state + heartbeat → determine live/retryable/needs-user-input → act accordingly → never reset state manually without an event record |
| **Agent runaway** | Cancel workflow → revoke task token → stop runtime/container → preserve trace + workspace snapshot → classify cause |
| **Secret exposure** | Revoke credential immediately → disable tool/provider → preserve relevant logs → assess data exposure → notify affected owner |
| **Sandbox compromise** | Isolate worker host → disable egress → snapshot evidence → rotate secrets → rebuild from trusted image |
| **DB / object store restore** | Restore to isolated environment → verify counts/checksums/ACLs → run task replay tests → document recovery point/time |
| **DGX Spark unavailable** | Fail over to allowed cloud provider or queue task → never silently violate a local-only privacy requirement |
| **Failed release** | Disable feature flag or roll back deployment → preserve migrations compatibility + release artifacts |

## Minimum dashboards

- Tasks created/completed/failed/cancelled by project and type.
- Queue depth, workflow age, blocked tasks, worker saturation.
- Model request volume, p50/p95 latency, errors, fallback rate, cost.
- Tool invocation success/failure/denial + approval wait time.
- Sandbox start/stop time, CPU/RAM use, cleanup failures.
- Memory retrieval latency, precision evaluation, ACL denial counts.
- Security alerts, rate limits, unusual external egress.

## SLO policy

Do not promise numeric production SLOs until a stable baseline exists. Instrument availability, task-start latency, API response latency, workflow recovery, artifact availability, approval delivery. Set initial internal objectives from ≥2 weeks of real workload observations, then publish with scope and measurement method.
