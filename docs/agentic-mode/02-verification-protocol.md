# Protocol 2 — Verification

Goal: make **false completion impossible**. A task reaches COMPLETED only when required acceptance criteria are met or explicitly waived with the waiver recorded. "The model said it's done" is not verification.

## The verification ladder (cheapest first)

| Level | Check | Cost | Catches |
|---|---|---|---|
| V0 | Schema validation of every payload | ~0 | Malformed plans/results before they propagate |
| V1 | Deterministic checks: tests, linters, type checks, build, checksums | low | Objective breakage |
| V2 | Acceptance-criteria evaluation against artifacts | low | Missing deliverables |
| V3 | Independent QA agent (different model/context than producer) | medium | Semantic gaps, spec drift |
| V4 | Human review at approval gates | high | Judgment calls, P3+ actions |

Run V0 always, V1 before V3 (never pay for semantic review of something that doesn't compile), escalate up only as far as needed.

## Producer ≠ verifier

- The verifier must not merely echo the producing agent. Prefer a **different model** and a **fresh context** for V3.
- The verifier receives: the subtask objective, acceptance criteria, artifact references, evidence refs — *not* the producer's self-assessment.

## Evidence rules

1. Every `AgentResult.status="completed"` must carry `evidence_refs` (tool outputs, citations, screenshots) or `tests[]`.
2. Artifacts carry checksums (sha256); a changed artifact after completion is a detected event, not a silent overwrite.
3. Claims-to-citations map for research: every factual claim links to a source with date.
4. Test results are persisted (exit codes, logs), not paraphrased.

## Failure classification

| Class | Meaning | Response |
|---|---|---|
| `transient_infra` | Timeout, rate limit, provider 5xx | Bounded retry (2) with exponential backoff + jitter |
| `agent_failure` | Wrong output, criteria not met | 1 retry with revised prompt/approach, then replan or WAITING_FOR_USER |
| `policy_denial` | Permission denied, allowlist violation | **No retry.** Surface to user; audit |
| `invalid_request` | Schema violation, malformed input | **No retry.** Fix the producer |
| `hard_constraint` | Budget exhausted, deadline passed, deadline constraint | FAIL terminal; user may open new attempt |

## Idempotency rules (side effects)

- Every side-effecting tool call carries an **idempotency key** derived from (task_id, subtask_id, action, payload-hash).
- Workflow retries must never duplicate an external action without reconciliation — check the action ledger first.
- Cancellation propagates: stop activities, revoke task tokens, clean workspaces, record unresolved external actions.

## State-machine enforcement

- `VERIFYING → COMPLETED` only with all required criteria green.
- `VERIFYING` failure routes to `RECOVERY` (bounded) or `BLOCKED`/`FAILED` — never silently back to `RUNNING`.
- Restart-safe: verification state lives in the event ledger, so a crashed worker resumes without re-running paid work.
