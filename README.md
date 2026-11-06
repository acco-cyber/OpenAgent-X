# OpenAgent-X

**The most auditable pure-stdlib agent framework.** Python 3.10+, zero
dependencies, zero network. Every observable action an agent takes becomes an
append-only journal event — inspectable, replayable, and redacted by default.
Grading is *honest*: golden-task drills execute real behavior offline and never
report a green check that did not actually run.

```
oax eval      # run every golden task drill, all green or exit 1   (13 tasks / 131 checks)
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
python3 -m openagentx examples # five runnable end-to-end demos
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
