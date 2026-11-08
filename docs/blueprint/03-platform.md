# Blueprint §9–12 — Memory, execution, security, data model

*Faithful port of HYDRION ONE blueprint v1.0 (2026-11-05). Proposed plan, not
a claim of implemented capability.*

## 9. Memory, knowledge and project context

Memory should make work continuous without turning uncertain model inferences
into unquestioned facts. The system needs distinct stores for conversation
context, user preferences, project decisions, knowledge documents, artifacts
and run history. Project memory is the MVP priority; personal cross-project
memory comes later and requires explicit controls.

### Memory domains

| Domain | Examples | Access policy |
|---|---|---|
| Task memory | Current plan, step outputs, error history, task summaries. | Visible to task participants and authorized project members. |
| Project memory | Architecture decisions, repository conventions, dataset facts, experiment results, open blockers. | Scoped to one project; retrieved only when project context matches. |
| User preference memory | Preferred formats, recurring workflow settings and explicit personalization choices. | User controlled; separate from confidential project data. |
| Knowledge corpus | Uploaded papers, docs, datasets descriptions, source snapshots and searchable notes. | Project-level ACL and source provenance. |
| Execution memory | Model choice, tool invocations, approvals, artifacts, tests and costs. | Audit/read permissions; retention policy applies. |

### Recommended data path

1. Ingest document or event and record source, owner, project, timestamp and
   access scope.
2. Parse and chunk content; preserve page/section/line metadata and content
   hashes.
3. Generate embeddings using a documented model and version; store vector
   plus text/metadata.
4. Retrieve by project filter, permission filter, semantic similarity,
   lexical match and recency.
5. Re-rank candidate passages and return provenance, confidence and source
   links.
6. Optionally summarize long task history into a memory candidate; do not
   automatically elevate it to durable memory.
7. Promote important facts/decisions to project memory with evidence and an
   editable status.
8. Allow correction, expiration, export and deletion; propagate deletion
   through derived indexes.

### Memory record

```json
{
  "memory_id": "uuid",
  "project_id": "uuid-or-null",
  "domain": "project|user|knowledge|execution",
  "type": "decision|fact|preference|procedure|artifact_summary",
  "content": "Use PostgreSQL as the source of truth",
  "source_refs": ["artifact:uuid", "task:uuid"],
  "confidence": 0.96,
  "status": "candidate|verified|superseded|rejected",
  "created_at": "ISO-8601",
  "expires_at": null,
  "visibility": "private|project|team"
}
```

### Retrieval and quality controls

- Apply access control before similarity search, not after result generation.
- Store exact source spans so claims can link back to documents.
- Detect contradictory records and mark them for resolution rather than
  choosing silently.
- Distinguish user-stated facts, imported document claims, agent hypotheses
  and verified outcomes.
- Avoid storing secrets, credentials, sensitive personal data or temporary
  prompt text as long-term memory.
- Provide a memory inspector with search, edit, pin, unpin, export and delete
  actions.

### MVP memory stack

PostgreSQL is the system of record. pgvector can provide vector similarity in
the same database, with ordinary relational filters for project and access
scope. Redis is for ephemeral caches and short-lived coordination, not the
authoritative memory store. An optional graph database should be deferred
until an evaluation shows that entity relationships add value beyond
relational links and retrieval.

## 10. Execution environments and computer use

### Workspace model

- One project has a stable logical workspace ID; each task gets an isolated
  execution instance.
- Mount only the relevant repository, input artifacts and temporary outputs.
- Never mount the host home directory or broad credential directories into an
  agent container.
- Use non-root users, read-only base images, resource quotas, process limits
  and short-lived credentials.
- Restrict outbound network access by default; open only approved domains or
  endpoints.
- Snapshot workspace before large or destructive edits; preserve the diff and
  execution logs.
- Upload final artifacts to object storage and tear down temporary compute
  when finished.

### Execution tiers

| Tier | Workload | Boundary |
|---|---|---|
| E0: read-only tools | Search, fetch, file inspection and metadata extraction. | No write credentials; content treated as untrusted. |
| E1: reversible local | Draft documents, local code edits, temporary files. | Per-task copy-on-write workspace; user can inspect and discard. |
| E2: sandboxed compute | Code execution, tests, notebooks, browser automation. | Container or VM; CPU/RAM/time quotas; restricted egress; isolated secrets. |
| E3: external side effects | Send email, create external issue/PR, publish content, modify external records. | Explicit approval bound to exact operation; idempotency key; post-action verification. |
| E4: privileged operations | Admin access, production deploy, destructive actions or financial operations. | Default disabled in MVP; explicit elevated auth, strong confirmation and full audit. |

### Browser and desktop policy

- Prefer browser automation isolated in a dedicated browser context over host
  browser control.
- Use per-project browser profiles and do not reuse personal sessions across
  projects.
- Mask passwords and recovery codes from model-visible page content and logs.
- Before form submission or purchase, show the exact action and destination
  to the user.
- Capture screenshots and DOM/action summaries before and after important
  operations.
- A webpage is untrusted input; page text cannot instruct the agent to reveal
  secrets or bypass policy.
- Host desktop integration is opt-in, read-only by default and visibly active
  when connected.

### Recovery and rollback

A runtime adapter must support create, inspect, pause, resume, terminate,
snapshot and artifact export where the underlying runtime permits. If a
runtime does not support one of these operations, the adapter declares that
limitation. HYDRION must never promise rollback of an external side effect
that cannot actually be reversed.

## 11. Security, permissions and threat model

Security is a core product feature because the system can read private files,
execute code, use browsers and act on external services. The policy service
must enforce tool permissions at invocation time. A system prompt is
guidance, not a security boundary.

Permission tiers (Figure 3, described): P0 READ ONLY → P1 REVERSIBLE → P2
SANDBOXED → P3 APPROVAL → P4 PRIVILEGED. Default deny. Permission is checked
by the policy service at tool execution time, not only in the prompt.

### Permission levels

| Level | Examples | Required control |
|---|---|---|
| P0 Read-only | Search, fetch, inspect files, summarize. | Project ACL, data classification, logging. |
| P1 Reversible local | Create a draft, copy a file, edit sandbox content. | Workspace isolation, diff preview, rollback/snapshot. |
| P2 Sandboxed execution | Run tests, install approved packages, operate isolated browser. | Container/VM boundary, quotas, egress policy, secret scoping. |
| P3 External side effect | Send, publish, create PR, update external database. | Human approval of exact action, destination and payload; idempotency. |
| P4 Privileged | Production deploy, destructive admin operation, financial transaction. | Disabled unless specifically enabled; re-authentication and high-assurance approval. |

### Threat model

| Threat | Example | Mitigation |
|---|---|---|
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

### Security implementation checklist

- OIDC-based identity and short-lived sessions.
- RBAC for user/admin/project roles; ABAC for resource sensitivity and action
  context.
- Project-level encryption and tenant-aware database access policies.
- Secrets vault or cloud secret manager; never store plaintext secrets in
  prompts or logs.
- Signed approvals linked to action hash, user, timestamp and expiration.
- Append-only audit records and correlation IDs across service boundaries.
- Container image pinning, SBOM generation, vulnerability scanning and
  dependency review.
- Rate limits, abuse detection, request-size limits and per-user spend
  ceilings.
- Backups with tested restoration and encrypted object storage.
- Incident response procedure: revoke credentials, disable integrations,
  isolate workers, preserve logs, inform affected users.

### Safety baseline for launch

> **RELEASE BLOCKER.** Do not launch unrestricted host shell access,
> persistent personal browser sessions, automatic purchase/payment actions or
> production deployment privileges in the MVP. These are separate security
> projects and need threat modeling and explicit approval semantics.

## 12. Data model, APIs and event contracts

### Core relational entities

| Entity/table | Key fields | Purpose |
|---|---|---|
| users | id, email/subject, role, status, created_at | Identity mapping and account lifecycle. |
| projects | id, owner_id, name, policy_id, created_at | Project scope, instructions and membership boundary. |
| project_members | project_id, user_id, role | Project authorization. |
| tasks | id, project_id, creator_id, objective, state, risk, budget, created_at | Canonical task record. |
| subtasks | id, task_id, agent_id, dependency_refs, state, acceptance_criteria | Delegated work graph. |
| workflow_events | id, task_id, sequence, event_type, payload, timestamp | Append-only state and action history. |
| agent_definitions | id, version, capabilities, limits, tool_allowlist | Versioned agent catalog. |
| agent_runs | id, subtask_id, runtime_id, model_id, usage, status | Execution record. |
| model_deployments | id, provider, model, capabilities, cost, health | Provider/model registry. |
| tool_registry | id, server, tool_name, schema, risk, version | Tool catalog and policy metadata. |
| approvals | id, task_id, action_hash, approver_id, decision, expires_at | Human approval evidence. |
| artifacts | id, task_id, project_id, uri, mime_type, sha256, size | Generated and input files. |
| memories | id, project_id, domain, content, source_refs, confidence, status | Project/user knowledge records. |
| credentials_refs | id, owner_id, provider, secret_ref, scope | References to secret manager entries; never raw secrets. |
| evaluations | id, run_id, suite, metric, value, config_hash | Benchmark and quality results. |

### Public API surface (initial)

| Method + path | Purpose |
|---|---|
| POST /api/v1/tasks | Create a task and return task ID plus initial state. |
| GET /api/v1/tasks/{task_id} | Read task state, plan summary and progress. |
| POST /api/v1/tasks/{task_id}/approve | Approve an action or plan version by approval token. |
| POST /api/v1/tasks/{task_id}/cancel | Request cancellation and cleanup. |
| POST /api/v1/tasks/{task_id}/resume | Resume after an explicit blocker is resolved. |
| GET /api/v1/tasks/{task_id}/events | Read ordered workflow events. |
| GET /api/v1/tasks/{task_id}/artifacts | List downloadable artifacts. |
| GET /api/v1/projects/{project_id}/memory | Search permitted project memory. |
| POST /api/v1/projects/{project_id}/memory | Create a candidate or verified memory record. |
| GET /api/v1/models/capabilities | List available model capability profiles, subject to policy. |
| GET /api/v1/agents | List available agent definitions. |
| POST /api/v1/tools/{tool_id}/invoke | Internal tool-gateway endpoint; not directly exposed to untrusted clients. |

### Task creation request example

```json
POST /api/v1/tasks
{
  "project_id": "prj_123",
  "objective": "Review the repository and implement the CSV export feature",
  "constraints": {
    "max_cost_usd": 8,
    "deadline": null,
    "allow_external_write": false
  },
  "deliverables": ["code_patch", "test_report", "implementation_summary"],
  "attachments": ["artifact_456"]
}
```

### Event envelope

```json
{
  "event_id": "uuid",
  "task_id": "uuid",
  "sequence": 42,
  "event_type": "agent.tool_call.completed",
  "occurred_at": "2026-11-05T12:00:00Z",
  "actor": {"type": "agent", "id": "coding@1.0.0"},
  "correlation_id": "uuid",
  "payload": {"tool": "pytest", "exit_code": 0},
  "redaction_applied": true
}
```

### Event naming

- task.created, task.planned, task.approval_requested, task.approved,
  task.started.
- subtask.dispatched, subtask.completed, subtask.failed.
- agent.started, agent.model_selected, agent.tool_call.started,
  agent.tool_call.completed.
- execution.workspace_created, execution.snapshot_created,
  execution.terminated.
- verification.started, verification.passed, verification.failed.
- artifact.created, artifact.downloaded, memory.candidate_created,
  memory.promoted.
- task.waiting_for_user, task.blocked, task.recovered, task.completed,
  task.failed, task.cancelled.
