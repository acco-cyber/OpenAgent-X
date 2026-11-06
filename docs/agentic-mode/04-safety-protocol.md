# Protocol 4 — Safety

Goal: full agentic power **under human authority**. Safety is an execution property — enforced by the policy service at tool-invocation time, never by prompt text.

## Permission tiers (default deny)

| Tier | Name | Examples | Control |
|---|---|---|---|
| P0 | Read-only | Search, fetch, inspect, summarize | Project ACL, data classification, logging |
| P1 | Reversible local | Draft, copy, edit sandbox | Workspace isolation, diff preview, rollback/snapshot |
| P2 | Sandboxed execution | Tests, approved installs, isolated browser | Container/VM boundary, quotas, egress policy |
| P3 | External side effect | Send, publish, create PR, update external DB | **Human approval of exact action + destination + payload; idempotency key** |
| P4 | Privileged | Production deploy, destructive admin, financial ops | **Disabled by default**; re-auth + high-assurance approval |

## Approval flow (P3+)

1. Agent proposes the action: destination, exact payload, permission level.
2. Policy service computes `action_hash = SHA-256(exact action/plan version)`.
3. UI shows the human: destination, payload, risk, expiry.
4. Human decision persists as an `Approval` record (hash-bound, expiring).
5. Execution checks the approval matches the **exact** hash — a one-byte payload change voids it.
6. Result + evidence recorded; unresolved cancellations are recorded, never retried silently.

## Execution boundaries

- E0 read-only → E1 reversible local (copy-on-write) → E2 sandboxed compute (container/VM, non-root, quotas, restricted egress) → E3 external effects (approval-gated) → E4 privileged (disabled by default).
- Never mount host home directories or credential dirs into agent containers.
- Restrict outbound network by default; open only approved domains.
- Snapshot before large/destructive edits; preserve diffs and logs.
- Runtime adapters declare which of create/inspect/pause/resume/terminate/snapshot they support — and OpenAgent-X never promises rollback of an irreversible external effect.

## Prompt-injection defense

Web pages, PDFs, tool results, and **other agents' messages are data, not instructions**:

1. Retrieved content enters the context marked as evidence, never as directives.
2. Tool allowlists per agent; deny controls surfaced in UI.
3. Approval gates on external side effects regardless of what the content "asked" for.
4. Red-team suite: page-instructs-agent payloads, secret-elicitation, permission-bypass attempts (part of release-blocking security tests).
5. Mask passwords/recovery codes from model-visible content; show destination before form submissions/purchases.

## Secrets discipline

- Secrets live in a secrets vault; tasks receive short-lived, task-scoped tokens — never the vault.
- Redaction at log/persistence boundaries (`redaction_applied: true` on events).
- No provider credentials in browser code, prompts, or artifacts. Ever.
- Incident path: revoke credential → disable tool/provider → preserve logs → assess exposure → notify owner.

## Threat model quick reference

| Threat | Mitigation |
|---|---|
| Prompt injection | Data/instruction separation, allowlists, approval gates, adversarial tests |
| Privilege escalation | Central policy check per invocation, short-lived tokens, no shared admin creds |
| Secret exfiltration | Secret broker, redaction, egress restriction, non-root sandbox |
| Cross-project leakage | Tenant/project filters **before** retrieval; authorization tests |
| Malicious dependency | Package allowlists, lockfiles, SBOM, sandbox |
| Runaway agent loop | Hard budgets, depth limits, cycle detection, kill switch |
| Replay/duplicate side effects | Idempotency keys, action ledger, reconciliation |
| Audit tampering | Append-only ledger, external log sink, signed artifact hashes |
