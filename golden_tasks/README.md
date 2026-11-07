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
| 08 | pack-roundtrip | pack (10) | deterministic manifests, hashes match independent hashlib, modified/extra/missing each detected |
| 09 | sbom-pure | sbom (10) | BOM purity verdict is computed: repo stdlib-only, imports classified, foreign flips verdict |
| 10 | team-handoff | team (12) | lead briefs on disk, reserved `handoff` event (reason recorded), specialist reads + answers after the handoff on one dense shared journal |
| 11 | router-fallback | router (10) | primary fails loudly, fallback serves the turn with every attempt logged, total outage stops `model_unavailable` without a fabricated reply |
| 12 | memory-recall | memory (10) | TF-IDF recall over past runs: right run ranked first, deterministic, unknown queries return nothing, memory is read-only and redaction-safe |
| 13 | compaction | compact (13) | tool pairs fold into `tool_fold {tool, ok, redactions}`, step bookkeeping dropped, run truth survives, original byte-identical, re-compaction deterministic |
| 14 | cache-replay | cache (10) | prompt-hash cache: exact repeats served without touching the inner adapter, keys canonical + order-sensitive, mutation cannot poison, cached run journals identically |
| 15 | hooks-deny | hooks (11) | deny policy fires before the registry: denied tool never executes, every decision journaled as `hook`, first match wins, agent observes and still replies |
| 16 | parallel-fanout | fanout (14) | one task → N real branch runs on their own journals: dispatch order kept, failures recorded as data (`script_error` + empty reply in fanin), parent run_id references verified in child journals, structural determinism on re-run |
| 17 | structured-output | structured (11) | messy replies repaired with exact note lists (fences, literals, trailing commas, smart quotes, extraction), hopeless input raises, schema rejects missing keys, wrong types and bool-as-integer |
| 18 | retry-backoff | retry (12) | transient faults recovered on a deterministic exponential schedule, every attempt logged, give-up raises loudly, plan bugs never retried, retried runs journal exactly like healthy ones |
| 19 | circuit-breaker | breaker (12) | consecutive real failures trip the circuit (original fault surfaced), open fast-fails without consulting the inner, exact cooldown rejections then one probe that closes or re-opens, runner stops `model_unavailable` without fabricating a reply |
| 20 | planner-executor | planner (14) | one planning turn fans out into real executor runs on their own journals: fenced plans repaired with exact notes and schema-validated before anything executes, plan bugs journal an error (never laundered into empty plans), failing steps are data with dense child journals referenced by the parent, structural determinism on re-run |
| 21 | snapshot-travel | snapshot (12) | checkpoints are pure prefix folds: later events and torn tails cannot rewrite an earlier checkpoint, travel is deterministic and monotone, bounds/order/density violations raise loudly, empty journal exposes exactly the zero state, reopened journals travel identically |
| 22 | prompt-layers | prompt (13) | includes expand depth-first in declared order (marker positions prove it), diamond includes expand once per path, cycles and self-includes report the full path, unknown layers and missing variables name themselves, over-deep acyclic chains rejected, substituted values stay literal so data never injects includes |
| 23 | tools-jit | jit (14) | turn-zero visibility is journaled before any step, undisclosed calls are refused with one `tool_hidden` event and zero side effects (no tool_call, no registry hit), `tools_expand` lands as an ordinary journaled call and makes its target visible, every visibility change is journaled with the full set and the additions, keyword matching is case-insensitive, capped rule disclosure truncates sorted without hiding the control plane, unknown expansion targets and rule tools name themselves, re-runs are event-for-event identical |
| 24 | chaos | chaos (14) | combined faults in ONE run: deterministic plan injects LLM outages and tool faults together, RetryLLM recovers with scars, every injection ledgered, faulted tool calls never execute (ghost write leaves no file), faulted results journaled as ordinary ok:false tool_results, event-type stream matches a healthy run, re-runs reproduce identical ledgers, bad plans name themselves |
| 25 | hash-chain | chain (14) | every chained line commits prev+digest over the full event JSON, edits (payload or ts) localize at the edited line, deletion/reorder break at the first mislinked line, head changes under tampering so a recorded seal exposes it, torn tails isolate with an intact but unsealable prefix, plain journals verify honestly as chained:false, empty journal reports the zero state, resume continues the chain, seal is loud |
| 26 | journal-diff | diff (12) | event-level diff: two runs of one script are semantically SAME (wall-clock ignored), self-diff is the zero diff, strict mode diverges at seq 0, edited replies localize at the reply's seq with both tails verbatim, deletions land removed / additions land added, torn tails isolate per side, type counts match the raw stream, renders byte-deterministic, CLI exits 0 same / 1 different |
| 27 | run-stats | stats (12) | the fingerprint IS replay's counters (one source of truth), type counts match the raw stream and sum to the total, planned tool profile (4 calls, 1 failure) visible, per-tool pairing sums with the failed read_file named, think counted as a tool, wall-clock span reported but never graded, empty journal exposes the zero state, torn tails honest with prefix counted, CLI exits 0 report / 1 missing |
| 28 | journal-bench | bench (12) | deterministic synthetic workload lands every planned event dense, three timed phases report honest wall-clock with positive rates, bytes re-statted from disk and read-back equals the plan, doubling the workload doubles the journal, zero-event bench exposes 0.0 rates instead of dividing by zero, render labels timings never-graded, structure stable across runs, no check ever asserts a timing value |
| 29 | fuzz-harness | fuzz (12) | seeded attack schedule (torn tail every 7th op, middle tear every 11th) fires exactly per seed, torn tails isolate + truncate to a dense resume, middle tears raise and restore byte-identically, payloads round-trip including unicode, two reads fold to one replay state, reports carry no timings (same seed -> same verdict), zero-op run still verifies, CLI exits 0 iff zero violations |
| 30 | property-suite | property (12) | invariants re-demanded after every step of a random trace (append / torn-tail / writer-restart lottery): density is exactly 0..n-1 after every step, every injected tear isolates and is strictly refused, truncation restores the exact pre-tear bytes byte-for-byte, the round-trip matches the written plan after every op, replay is ts-independent (a shifted wall-clock folds identically and semantic diff says same), reports deterministic (same seed -> same verdict), restarts resume dense, zero-op run verifies, CLI exits 0 iff zero violations |

Run: `python3 -m openagentx eval` (all green or exit 1). Current: **30 tasks, 342 checks**.

## Adding a task (rules)

1. JSON: `{id, title, drill, task_text, max_steps, script[], expect{}}`.
2. Script turns are single-line JSON (`{"action":{...},"thought":...}` / `{"reply":...}`).
3. Shape per drill family: runner drills need `script[]`; `team` needs
   `lead_script[]` + `specialist_script[]`; `router` needs `fallback_script[]`
   (the primary/failure adapters are fault-injected by the drill itself);
   `memory` needs `runs[].script[]` + `queries[]` (journals are generated by
   the drill itself); `hooks` needs `script[]` + `hooks.rules[]`;
   `fanout` needs `branches{}` (every branch with `script[]`) +
   `coordinator_script[]`; `structured` needs `script[]` + `cases[]` +
   `schema{}`; `retry`/`breaker` need `script[]` (fault doubles are
   injected by the drills themselves, tuned via `expect`); `planner` needs
   `planner_script[]` + `step_scripts[][]`; `snapshot` needs `script[]` +
   `expect.checkpoints[]`; `prompt` needs `layers{}` + `entry` +
   `expect.render`; `audit` needs
   `expect.planted_*`; `pack`/`sbom` need no
   script at all.
4. Any fixture secret must be runtime-concatenated inside Python — never in JSON.
5. Checks must observe real behavior from *this* run; no snapshots/caches.
6. Update `scripts/verify.mjs` drill allowlist when adding a new drill.
7. Eval count must never regress; new checks attach to new or existing tasks.
