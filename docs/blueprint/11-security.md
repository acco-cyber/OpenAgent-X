# 11. Security, permissions and threat model

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 11. Adapted for OpenAgent-X.

Security is a core product feature because the system can read private files, execute code, use browsers and act on external services. The policy service must enforce tool permissions at invocation time. A system prompt is guidance, not a security boundary.

Figure 3 (Permission tiers): all actions default to deny unless explicitly allowed.

## Permission levels

| Level | Examples | Required control |
| --- | --- | --- |
| P0 Read-only | Search, fetch, inspect files, summarize. | Project ACL, data classification, logging. |
| P1 Reversible local | Create a draft, copy a file, edit sandbox content. | Workspace isolation, diff preview, rollback/snapshot. |
| P2 Sandboxed execution | Run tests, install approved packages, operate isolated browser. | Container/VM boundary, quotas, egress policy, secret scoping. |
| P3 External side effect | Send, publish, create PR, update external database. | Human approval of exact action, destination and payload; idempotency. |
| P4 Privileged | Production deploy, destructive admin operation, financial transaction. | Disabled unless specifically enabled; re-authentication and high-assurance approval. |

## Threat model

| Threat | Example | Mitigation |
| --- | --- | --- |
| Prompt injection | A webpage or PDF instructs an agent to expose credentials or ignore prior rules. | Treat retrieved content as data; separate instructions and evidence; tool allowlists; approval gates; adversarial tests. |
| Privilege escalation | A specialist agent calls an admin tool outside its task scope. | Central policy check on every invocation; short-lived tokens; no shared admin credentials. |
| Secret exfiltration | A code process reads environment variables and posts them externally. | Secret broker, redaction, no secrets in default env, egress restrictions, non-root sandbox. |
| Cross-project leakage | Retrieval returns a document from another project. | Tenant/project filters before retrieval; authorization tests; separate object prefixes and encryption keys where appropriate. |
| Malicious dependency | Agent installs package with post-install script or malware. | Allowlisted packages, lockfiles, package cache, sandbox, provenance/SBOM and restricted network. |
| Runaway agent loop | Repeated retries or delegation consume budget indefinitely. | Hard token/time/tool budgets, depth limits, cycle detection, global kill switch. |
| Replay / duplicate side effects | Workflow retry submits same payment or email twice. | Idempotency keys, precondition checks, action ledger and reconciliation. |
| Audit tampering | Agent alters its own logs or removes evidence. | Append-only event ledger, separate service account, external log sink and signed artifact hashes. |
| Model/provider compromise | Provider endpoint returns malicious content or leaks prompts. | Provider allowlist, data policy, no blind trust, contract testing and local option for restricted data. |
| Unsafe computer control | A desktop agent clicks wrong control or changes wrong account. | Task-scoped session, screenshot confirmation, approval and action verification. |

## Security implementation checklist

- OIDC-based identity and short-lived sessions.
- RBAC for user/admin/project roles; ABAC for resource sensitivity and action context.
- Project-level encryption and tenant-aware database access policies.
- Secrets vault or cloud secret manager; never store plaintext secrets in prompts or logs.
- Signed approvals linked to action hash, user, timestamp and expiration.
- Append-only audit records and correlation IDs across service boundaries.
- Container image pinning, SBOM generation, vulnerability scanning and dependency review.
- Rate limits, abuse detection, request-size limits and per-user spend ceilings.
- Backups with tested restoration and encrypted object storage.
- Incident response procedure: revoke credentials, disable integrations, isolate workers, preserve logs, inform affected users.

## Safety baseline for launch

RELEASE BLOCKER: do not launch unrestricted host shell access, persistent personal browser sessions, automatic purchase/payment actions or production deployment privileges in the MVP. These are separate security projects and need threat modeling and explicit approval semantics.
