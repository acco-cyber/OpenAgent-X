# Changelog

All notable changes to OpenAgent-X. Dates are ISO-8601; claims are gated —
the checks named here are the same ones `oax eval` and `scripts/verify.mjs`
run on every commit (and in CI).

## [Unreleased]

### Added — examples

- Two gallery demos the stretch list still owed: example 26
  (`26_author_your_own_drill.py`) makes the tutorial's hero capstone
  runnable — author a task spec from scratch, grade a real offline run
  through `run_golden_task`, and watch the honest failures (a wrong
  expectation red by name, a crashing drill folded into
  `harness_error`, an unknown drill reported) before the repaired spec
  goes green; example 27 (`27_views_tour.py`) walks one real run through
  every read-only view — timeline, report, stats, grep, self-diff,
  replay-from, dashboard, mermaid — with byte-identical re-renders, one
  replay fold behind every counter, and a tour-wide sweep proving the
  raw fixture token appears in no view. README quickstart counts
  twenty-seven demos; the gallery table carries both rows; manifest 143
  files.

### Added — docs

- Per-drill explainers: `docs/explainers.md` gives every golden task its
  prose — what the run does, which invariants the checks grade (with the
  real check counts), and what a loud failure looks like — grouped by the
  job the code does, the same lens as `docs/modules.md`; the explainer
  gate in `scripts/verify.mjs` keeps the page welded to the matrix (a
  task without its entry fails the build; an entry without a task fails
  it from the other direction); README's documentation map and tutorial
  Step 10 link it; manifest 141 files.

### Added — presentation

- README professional overhaul: a programmatic banner (rendered art, no
  AI-generated text), a navigation table, a **Watch it run** section with a
  35-second demo recorded from a real session against a clean clone —
  clone → `oax doctor` (6/6) → `oax eval` (38 tasks, 435/435 green) →
  `oax run --timeline` (live redaction at the boundary) → `oax stats` →
  `oax grep` — every visible line is the tool's actual stdout, shipped as
  `docs/assets/demo.gif` (plays inline everywhere) plus `docs/assets/
  demo.mp4` (crisp H.264); a **Why developers use it** section naming six
  concrete ways the repo helps working engineers (reference patterns,
  stealable eval harness, flight recorder, security defaults, zero-install
  friction, honesty as discipline); a Contributing section stating the
  repo's enforced rules; the full clone URL replacing the placeholder; and
  the stale "35 golden drills" claim in the comparison table trued up to
  38. Assets are manifest-tracked (140 required files).

### Added — views

- `oax replay --from N`: the journal folds from the middle, honestly.
  `replay_from` folds every event with `seq >= N` from zero at that
  point; bounds are honest (`0..max seq`, an empty journal exposes only
  the zero state at 0, out-of-bounds raises `ValueError` — never silent
  clamping); density is required, so a gapped journal is an integrity
  failure that raises instead of folding; additivity is claimed only
  where it is true (every monotone counter of the suffix equals whole
  minus prefix) and never where it is false (`runs_open` is clamped,
  `last_reply`/`final_stop` describe only their own window); a torn tail
  is invisible to the fold and reported; the state is the view and
  renders through the redaction engine, so a raw secret on disk never
  leaves it even inside `last_reply`; the render names its window and is
  byte-deterministic. CLI exits 0 folded / 1 missing journal / 2 bad
  bounds with redacted stdout. Graded by golden task 38 (12 checks) and
  demonstrated by `examples/25_replay_from.py`.

### Added — views (grep)

- `oax grep`: the journal is searchable truth, not just replayable truth.
  `grep_journal` filters one journal's events with plain deterministic
  matchers all AND-ed together (case-sensitive substring over the
  type+payload JSON projection, exact event type, exact payload tool name,
  a `since_seq` floor, a `limit` cap kept in seq order); every match
  renders through the redaction engine, so raw secrets that live on disk
  can never leak through the search view — searching for the raw token
  itself matches (the disk is the truth) and still prints only
  `[REDACTED:github_token]`. Torn tails are isolated, never searched, only
  reported; the empty result is honest; output is byte-deterministic; CLI
  exits 0 matched / 1 no matches or missing journal. Graded by golden task
  37 (12 checks) and demonstrated by `examples/24_grep_journal.py`.

## [1.0.0] — 2026-11-07

Final release of the Epoch 3 rebuild (parts 1–25). Pure stdlib, Python
3.10+, offline by construction. Golden matrix: **36 tasks, 411 checks, all
green**; `oax audit .`: **0 findings**; doctor: **6/6**; 23 runnable
examples; 131 required files, all enforced.

### Added — release engineering

- The release-sweep drill (golden task 36): one real run re-demands the
  core invariants end-to-end — counters agree with the raw stream (one
  source of truth), report/trace/dashboard/mermaid re-render
  byte-identically, the self-diff is the zero diff, a runtime-assembled
  raw token is re-redacted by both rendered views, a chained journal
  verifies + seals + verifies, the repo audits to 0 findings, doctor
  passes 6/6.
- Release metadata is mechanically consistent: `__version__` must equal
  the top `CHANGELOG.md` entry, checked on every eval run by the sweep —
  a version bump that forgets the changelog (or the reverse) is a red
  drill.
- `examples/23_release_sweep.py` performs the sweep's story on a real run
  and grades the real drill 12/12 green.
- `docs/retrospective.md` reviews the 24-hour sprint honestly: three
  epochs, what was built, what the deliberate costs bought, what surprised
  us — with the gate that proves every number.

### Changed

- `__version__` 1.0.0-rc1 → 1.0.0. The candidate's promises are the
  release's promises — the same gates, the same matrix, one drill bigger.

## [1.0.0-rc1] — 2026-11-07

First release candidate of the Epoch 3 rebuild (parts 1–24). Pure stdlib,
Python 3.10+, offline by construction. Golden matrix: **35 tasks, 399
checks, all green**; `oax audit .`: **0 findings**; doctor: **6/6**.

### Added — core engine

- Append-only JSONL journal with dense sequences and torn-tail isolation;
  replay is a pure fold of the events — a function of events, never of the
  clock.
- Redaction engine at the journal boundary, re-applied by every rendered
  view (defense in depth); `oax audit .` is the always-on mechanical check.
- `ScriptedLLM` offline adapter, sandboxed builtin tools, event-sourced
  `AgentRunner` turn loop, team handoff runner (`handoff` is a control-plane
  tool call, never a journaled tool call), `FallbackRouter` with honest
  `model_unavailable` stops.
- The four honest stop reasons — `reply`, `max_steps`, `budget`,
  `stop_tool`/`stop` — each observable in `run_end`.
- `oax doctor` purity + integrity gate (6 checks) and `oax audit` secret
  scan; both are CI gates too.

### Added — orchestration

- Budget governor (`max_tool_calls`): stops *before* the capped call, names
  the refused tool with used/cap, cap recorded at `run_start`.
- `HookPolicy` deny rules fired before the registry; every decision (allows
  included) is a journaled `hook` event; refused calls leave zero side
  effects.
- JIT tool disclosure: tools invisible until disclosed, refusals before
  hooks with one `tool_hidden` event, re-runs event-for-event identical.
- Layered prompts (depth-first includes, cycle reporting, literal
  substitution), planner-executor (schema-validated plans, per-step sub-agent
  journals), snapshot travel (pure prefix folds), parallel fan-out (branch
  outcomes as data), structured output (`parse_json_loose` repair notes +
  lite schema validation where `True` is never an integer), prompt-hash
  response cache (hits are deep copies), TF-IDF memory over past journals,
  honest compaction (`oax compact` never touches the source).

### Added — reliability

- `RetryLLM` with deterministic exponential backoff (retries invisible to
  the journal, give-up loud, plan bugs never retried) and `CircuitBreaker`
  (trip surfaces the original fault, tick-clock cooldown, probe closes or
  re-opens).
- `ChaosLLM`/`ChaosTools`: combined faults in one run on a fixed plan, every
  injection ledgered, faulted calls never execute.
- Hash-chained journals (`{prev, digest}` per line): edits, deletions and
  reorderings are detected and localized to the exact seq; torn tails
  isolate; plain journals verify honestly as `chained: false`.
- Seeded fuzz over the journal contract, property suite that re-demands
  invariants after every random trace step, throughput microbench
  (`oax bench`) whose numbers are observations, never grades.

### Added — views and analytics

- `oax diff`: event-level journal diff — semantic mode ignores wall-clock,
  `--strict` compares every stored byte, `diverged_at` names the split, exit
  code is a contract (0 = same).
- `oax stats`: numeric fingerprint taken from replay's own counters (one
  source of truth, two views cannot disagree).
- `oax dashboard`: byte-deterministic self-contained HTML (inline CSS, zero
  external assets, no timestamps); `oax mermaid`: deterministic escaped
  flowchart export.

### Added — supply chain

- `oax pack`: deterministic tree manifest; `oax pack2`: HMAC-SHA256 signed
  manifests (wrong key / edited entry / tampered file each fail their own
  named layer); `oax sbom`: stdlib bill of materials whose purity verdict is
  computed; `oax graph`: import dependency graph with eager/lazy edges,
  longest-path layers and Tarjan cycle detection.

### Added — evaluation

- 35 golden tasks / 399 checks over 34 drills; exceptions fold into a
  failing `harness_error` check; check count only moves forward.
- `oax eval --workers N`: drills on a stdlib thread pool, verdicts proven
  identical to the serial run (parallelism changes the wall-clock, never the
  grade); per-task wall-clock reported on every line.

### Added — docs, CI, community

- `docs/tutorial.md` (ten zero-to-hero steps, every snippet executed before
  commit), `docs/modules.md` (39 module guides), ten ADRs, `docs/glossary.md`
  (30 terms), `docs/faq.md` (15 honest answers).
- README with demo traces (one real run shown three ways), architecture
  diagram, honest comparison table, documentation map.
- CI (`.github/workflows/ci.yml`): the seven local gates on Python 3.10 and
  3.12 with zero install steps and no secrets; `scripts/verify.mjs` gates
  keep golden contracts, module guides, tutorial, ADR pack, README and the
  workflow itself in enforced sync.
- CONTRIBUTING, CODE_OF_CONDUCT, SECURITY (private vulnerability reporting),
  bug-report template that asks for the journal.

### Changed

- `build_depgraph` reuses the SBOM's parsed trees: one read + one parse per
  module feeds both the BOM and the graph (eval wall-clock median 1.349s →
  1.247s serial, 1.772s → 1.569s with `--workers 4` on the dev machine;
  timings are observations, not claims about your hardware).

### Deliberate costs (documented in the ADRs)

- No third-party imports, no network modules, no async, no real-model
  adapters in the package (ADR-0002, ADR-0004). The adapter boundary is the
  integration point; everything upstream already honors the contract.
