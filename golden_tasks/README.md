# Golden Tasks — the honest grading matrix

Each task is an offline, deterministic JSON spec executed against the real
runner + tools, graded by a drill of named checks. Exceptions fold into a
failing `harness_error` check. The matrix only grows.

| # | Task | Drill | Focus |
|---|---|---|---|
| 01 | loop-stop | loop (9) | deterministic stop on reply, dense seq, reopen stability |
| 02 | boundary-redaction | redact (8) | secrets redacted at journal boundary; raw truth only on disk |
| 03 | trace-torn-resume | trace (9) | torn-tail isolation, replay determinism, views agree, resume |
| 04 | loop-budget | budget (10) | `max_tool_calls` governor: budget event names the rejected call, cap at run_start, capped attempt counts a step |
| 05 | stop-tool | stop (10) | reserved `stop` tool: reason in run_end, never a tool_call, prior work preserved |
| 06 | redact-nested | redact_nested (10) | deep redaction: bundle secrets marked at leaves, structure + plain fields intact, views re-redact |
| 07 | audit-self | audit (10) | scanner finds planted runtime literals (kind/file/line, redacted snippet), repo self-audit 0 |

Run: `python3 -m openagentx eval` (all green or exit 1). Current: **7 tasks, 66 checks**.

## Adding a task (rules)

1. JSON: `{id, title, drill, task_text, max_steps, script[], expect{}}`.
2. Script turns are single-line JSON (`{"action":{...},"thought":...}` / `{"reply":...}`).
3. Any fixture secret must be runtime-concatenated inside Python — never in JSON.
4. Checks must observe real behavior from *this* run; no snapshots/caches.
5. Update `scripts/verify.mjs` drill allowlist when adding a new drill.
6. Eval count must never regress; new checks attach to new or existing tasks.
