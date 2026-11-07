# OpenAgent-X

**The most auditable pure-stdlib agent framework.** Python 3.10+, zero
dependencies, zero network. Every observable action an agent takes becomes an
append-only journal event — inspectable, replayable, and redacted by default.
Grading is *honest*: golden-task drills execute real behavior offline and never
report a green check that did not actually run.

```
oax eval      # run every golden task drill, all green or exit 1   (19 tasks / 201 checks)
oax doctor    # environment + pure-stdlib purity gate
oax audit .   # secret scan of the whole tree (0 findings or exit 1)
oax pack .    # deterministic tree manifest (build + --check verify)
oax sbom .    # stdlib bill of materials — purity verdict is computed (exit 1 if not pure)
oax recall    # TF-IDF memory over past-run journals (read-only, deterministic)
oax compact   # fold a journal into a denser copy; original never touched
oax examples  # execute every offline example end-to-end
```

Quickstart (no API keys, ever):

```
git clone <this repo> && cd OpenAgent-X
python3 -m openagentx doctor   # purity gate: pure stdlib, no network modules
python3 -m openagentx eval     # the honest golden matrix, all green or exit 1
python3 -m openagentx examples # eight runnable end-to-end demos
```

## What the agent runtime guarantees

- **Budget governor** — `max_tool_calls` stops the loop *before* the rejected
  call; the `budget` event names the tool that was refused, the cap is recorded
  at `run_start`, and a capped attempt still counts as a step.
- **Reserved control plane** — `stop` and team `handoff` are never journaled as
  tool calls; a stop carries its reason in `run_end`, a handoff switches the
  active role and hands delegated context to the specialist through the journal.
- **Model routing** — `FallbackRouter` walks its adapter chain per turn, logs
  every attempt honestly, and a total outage stops `model_unavailable` — never
  a fabricated reply.
- **Memory over past runs** — `MemoryLite` builds a TF-IDF index from what the
  redacted journals already say; recall is deterministic, read-only, and can
  never surface a raw secret or hallucinate a hit for an unknown query.
- **Honest compaction** — `oax compact` folds adjacent tool pairs into
  `tool_fold` events and drops loop bookkeeping in a new file; the source
  journal stays byte-identical and a torn source is refused, never laundered.
- **Prompt-hash cache** — `CachedLLM` serves exact-prompt repeats from a
  SHA-256-keyed store without calling the inner adapter; hits are deep copies
  (mutation cannot poison), counters are honest, and a cached run journals
  exactly like a computed one.
- **Deny-policy hooks** — `HookPolicy` rules fire before the registry: a
  denied call produces a journaled `hook` event and zero side effects, the
  agent observes the denial and adapts, and a run without a policy is
  untouched (zero hook events).
- **Parallel fan-out** — `FanoutRunner` dispatches one task to N real branch
  agents on their own journals, records every branch outcome on the parent
  journal (a failing branch is data, not a crash), and the coordinator
  answers only from the fanin; re-runs are structurally identical.
- **Structured output** — `parse_json_loose` repairs fences, trailing
  commas, Python literals, smart quotes and prose-wrapped JSON with honest
  repair notes; hopeless input raises loudly, and `validate_schema` catches
  wrong types (including `True` masquerading as an integer).
- **Retry with backoff** — `RetryLLM` recovers transient adapter failures on
  a deterministic exponential schedule; every attempt is logged, give-up
  raises loudly, plan bugs are never retried, and retries stay invisible to
  the journal.
- **Circuit breaker** — `CircuitBreaker` trips after consecutive real
  failures (surfacing the original fault), fast-fails without touching the
  dead dependency, cools down call-by-call, and one probe closes or re-opens
  it with an honest snapshot.

## Why it matters

| Property | Guarantee |
|---|---|
| **Event-sourced** | Agent behavior is a journal of events; the journal is the truth |
| **Append-only** | Sequences are dense; torn tails are isolated, never silently dropped |
| **Redaction by default** | Secrets entering tool args/results are redacted at the journal boundary |
| **Offline first** | The full eval matrix runs with zero API keys via `ScriptedLLM` |
| **Honest grading** | Drill exceptions fold into a failing `harness_error` check — no silent passes |
| **Pure stdlib** | `oax doctor` fails if a non-stdlib import ever sneaks in |

## Status & roadmap

- **Epoch 3 (recovery rebuild)** — see `docs/24h-plan.md`. Two prior epochs were
  lost to sandbox recycling; this one lives on the durable volume.
- Golden tasks grow with every feature slot; eval count only ever moves forward.

## Layout

```
openagentx/     the library (events, runner, tools, trace, evaluation, ...)
golden_tasks/   offline drill specs (JSON) — the grading matrix
examples/       runnable offline examples (zero API keys)
scripts/        verify.mjs, required-files.txt
docs/           AI context, sprint plan
```

MIT licensed. Built to be audited.
