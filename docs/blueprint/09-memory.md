# 9. Memory, knowledge and project context

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 9. Adapted for OpenAgent-X.

Memory should make work continuous without turning uncertain model inferences into unquestioned facts. The system needs distinct stores for conversation context, user preferences, project decisions, knowledge documents, artifacts and run history. Project memory is the MVP priority; personal cross-project memory comes later and requires explicit controls.

## Memory domains

| Domain | Examples | Access policy |
| --- | --- | --- |
| Task memory | Current plan, step outputs, error history, task summaries. | Visible to task participants and authorized project members. |
| Project memory | Architecture decisions, repository conventions, dataset facts, experiment results, open blockers. | Scoped to one project; retrieved only when project context matches. |
| User preference memory | Preferred formats, recurring workflow settings and explicit personalization choices. | User controlled; separate from confidential project data. |
| Knowledge corpus | Uploaded papers, docs, datasets descriptions, source snapshots and searchable notes. | Project-level ACL and source provenance. |
| Execution memory | Model choice, tool invocations, approvals, artifacts, tests and costs. | Audit/read permissions; retention policy applies. |

## Recommended data path

1. Ingest document or event and record source, owner, project, timestamp and access scope.
2. Parse and chunk content; preserve page/section/line metadata and content hashes.
3. Generate embeddings using a documented model and version; store vector plus text/metadata.
4. Retrieve by project filter, permission filter, semantic similarity, lexical match and recency.
5. Re-rank candidate passages and return provenance, confidence and source links.
6. Optionally summarize long task history into a memory candidate; do not automatically elevate it to durable memory.
7. Promote important facts/decisions to project memory with evidence and an editable status.
8. Allow correction, expiration, export and deletion; propagate deletion through derived indexes.

## Memory record

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

## Retrieval and quality controls

- Apply access control before similarity search, not after result generation.
- Store exact source spans so claims can link back to documents.
- Detect contradictory records and mark them for resolution rather than choosing silently.
- Distinguish user-stated facts, imported document claims, agent hypotheses and verified outcomes.
- Avoid storing secrets, credentials, sensitive personal data or temporary prompt text as long-term memory.
- Provide a memory inspector with search, edit, pin, unpin, export and delete actions.

## MVP memory stack

PostgreSQL is the system of record. pgvector can provide vector similarity in the same database, with ordinary relational filters for project and access scope. Redis is for ephemeral caches and short-lived coordination, not the authoritative memory store. An optional graph database should be deferred until an evaluation shows that entity relationships add value beyond relational links and retrieval.
