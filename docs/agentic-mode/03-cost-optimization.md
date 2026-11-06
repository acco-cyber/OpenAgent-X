# Protocol 3 — Cost Optimization

Goal: **highest productivity per dollar**. Agentic cost explosions come from three habits: powerful-model-for-everything, context bloat, and retry storms. Each has a structural fix.

## 1. The model-profile ladder (cheapest sufficient tier first)

| Step | Profile | Use for | Typical cost class |
|---|---|---|---|
| 1 | `fast` | Classification, extraction, titles, routing, formatting, simple transforms | $ |
| 2 | `balanced` | Summarization, routine agent work, drafting | $$ |
| 3 | `reasoning` | Complex planning, multi-step diagnosis, math | $$$$ |
| 4 | `coding` | Repo-level patches, test repair | $$$ |
| 5 | `vision` | Screenshots, charts, document images | $$$ |
| 6 | `local-private` | Sensitive data, offline work, high-volume embeddings | infra |

**Escalation rule:** start 1–2 steps below your guess. Escalate only on *measured* failure (V1/V2 checks failed, not "it felt dumb"). **De-escalate** after two successes at a lower tier. Record every selection + reason (`agent.model_selected` event) — the log becomes your routing evidence base.

### Role defaults

| Role | Default profile | Escalate when |
|---|---|---|
| Orchestrator/planner | `reasoning` for the plan, `fast` for bookkeeping | Plan validation fails twice |
| Research | `balanced` | Cross-source synthesis stalls |
| Coding | `coding` | — |
| Data | `balanced` + sandboxed execution | Statistical reasoning needed |
| QA verifier | `balanced` (different model than producer) | Subtle semantic criteria |
| Memory curation | `fast` | Contradiction resolution |

## 2. Budget enforcement (hard ceilings, not suggestions)

- Every subtask carries `max_tokens` + `max_tool_calls` (+ optional wall clock) — from `plan.schema.json`.
- Orchestrator enforces: budget at 80% → emit warning event; 100% → stop, classify (`hard_constraint`), replan or ask.
- Tool-call budgets: read-only research may be generous; write-enabled agents are tight.
- Global kill switch + per-user spend ceilings live in the policy service, not prompts.

## 3. Context compression (the biggest silent cost)

- **Pass references, not copies.** Agents get `artifact:uuid` / `memory:uuid` pointers and fetch on demand — never a 50KB dump in the prompt.
- **Summarize, don't replay.** Long histories become memory *candidates*; only promoted decisions re-enter context.
- **Scope retrieval.** Project + permission filters *before* similarity search; top-k small; re-rank rather than flood.
- **Structured outputs over prose.** JSON Schema outputs prevent "explain your reasoning in 800 words" tax and make results machine-checkable without a second LLM pass.

## 4. Cache and batch

- Provider-level: enable prompt caching where the provider supports it (system prompts, large stable context).
- App-level: memoize tool results by (url/params hash) per project; a re-fetch of the same page is a bug.
- Batch embeddings and bulk classifications; they're rate-limited, not latency-critical.

## 5. Retry hygiene

- Exponential backoff **with jitter** for transient infra errors only.
- Never retry: authorization denials, invalid requests, policy denials (each retry is pure cost + risk).
- One revised-approach retry for agent failure *before* escalating the model — a better prompt is usually cheaper than a bigger model.

## 6. Measure, then tune

Track per task/subtask: tokens in/out, tool calls, cost, p50/p95 latency, V1-pass-rate at each tier, escalation frequency, fallback rate. Tune the routing weights (`w_cost`, `w_quality`, …) from this evidence — **not** from vibes. Avoid optimizing purely for cheapest-token: tool reliability, structured-output validity and task success are the real denominators.

## Anti-patterns

- ❌ Frontier model writes every subtask's JSON.
- ❌ Full history re-sent each turn "for safety".
- ❌ Unlimited retries "until it works".
- ❌ Semantic QA on code that doesn't compile.
- ❌ Re-fetching the same search results in a loop.
- ✅ Cheap model classifies → mid model drafts → strong model plans/patches → verifier checks → evidence recorded.
