# Changelog

All notable changes to OpenAgent-X. Dates are ISO-8601; claims are gated —
the checks named here are the same ones `oax eval` and `scripts/verify.mjs`
run on every commit (and in CI).

## [Unreleased]

### Added — tamper evidence from the CLI (chain)

- `oax chain <journal>`: the hash chain's module API (seal /
  verify_journal / chain_report) was reachable only from Python; the
  operator surface now matches the guarantee. Verify mode prints the
  deterministic one-line verdict and exits 0 intact / 1 when the chain
  is broken, the tail is torn or the path is missing — a torn tail is
  an incomplete file: the intact prefix still reports ok but the CLI
  refuses exit 0 with the `+torn_tail` mark, and a missing path is
  named (read_events_safe would otherwise bless an absent file as ok).
  `--seal` prints the 64-hex head of a fully intact chain-written
  journal; every ChainError refusal (torn, broken, empty, not
  chain-written) is a named one-line rejection, never a traceback.
  `chain_report` gains an optional precomputed report so the CLI
  verifies once and renders once. Graded by golden task 44 (12 checks)
  tampering with real journal copies in fresh temp workspaces — edits,
  deletions and reorders localized at the first mislinked index — and
  demonstrated by example 33; matrix 44 tasks / 510 checks.

### Added — the auditor audits itself (doctor)

- the doctor's gates are now graded at their failure edges: golden task 43
  drives `openagentx/doctor.py` over the real tree (6/6) and over fresh
  temp workspaces planted with the defects the gates exist to catch — a
  third-party import caught by `stdlib_purity` with `foreign.py:numpy`
  named, a `socket` import caught by `offline_purity`, a missing
  required file named, a truncated spec folded into
  `golden_tasks_valid` carrying the real exception without crashing the
  doctor, an unknown drill named, and the gates proven independent (one
  poisoned tree turns exactly the four planted gates red); the verdict
  render moved into `render_doctor` as a pure function of the gate list
  (byte-identical output, docstring examples graded — floor now 20
  modules / 71 examples); the drill's first run caught `sys` missing
  from evaluation's imports and was root-fixed, and its docstring
  example on `render_doctor` caught an expected FAIL line one space
  short — both fixed at the root, not loosened; matrix 43 tasks / 498
  checks, demonstrated by example 32.

### Added — the multi-run index (runs)

- `oax runs [dir]`: a directory of journals becomes one honest table —
  `index_runs(dir)` scans `*.jsonl` sorted by file name and every row's
  counters come from the same `run_stats` the single-journal view uses
  (one grading path — the index can never disagree with `oax stats`);
  counters and flags only, never payload text (a journal is raw secrets
  on disk) and no path beyond the file name; torn tails are flags, not
  filters — the intact prefix counts and the row says `torn`, while a
  journal torn in the middle folds into a loud error row carrying the
  real exception with the redundant directory prefix stripped; additivity
  claimed only where true (events and tool counters sum across journals,
  durations never — spans overlap); zero journals is honest emptiness
  (`ok` False, exit 1 through the CLI); rows render byte-identically,
  the machine artifact carries the per-row counters under `sort_keys`
  with no directory path; graded by golden task 42 (12 checks — its
  first run caught the drill's own totals assertion saying 11 events
  where the real sum was 10, corrected against the sum) and demonstrated
  by example 31; matrix 42 tasks / 486 checks.

### Added — release attestation (attest)

- `oax attest [root] [--json PATH]`: one command, one artifact, every
  gate — `collect_gates(root)` runs doctor (purity + integrity),
  audit (0 findings), doctests (every docstring example green), the
  manifest (the tree hashes identically twice) and the matrix (every
  golden-task spec has its prose) in fixed order and folds them into
  one verdict; a gate that crashes folds red carrying the real
  exception, an empty gate list is never green, the human render is
  counters-only (no hash, no path, no wall-clock, byte-identical
  across calls) while the machine artifact (sort_keys JSON) carries
  the root path and the 64-hex tree hash so a byte-compare means the
  tree moved; the gates are root-parametric — package-mode doctest
  imports when the root is the running package, bare-file mode
  otherwise, a tree with no package is a loud red, never a skip; the
  CLI exits 0 green / 1 any gate red; graded by golden task 41 (12
  checks, eval floor 40 → 41, matrix 41 tasks / 474 checks) in a fresh
  child interpreter — the doctest drill's stdout discipline,
  inherited — and demonstrated by example 30; attest.py itself carries
  six curated `>>>` examples graded by `oax doctest` (floor 18 modules
  / 59 examples); modules.md, the CLI table, the tutorial and the
  explainer page synced; manifest 147 files

### Added — self-checks (doctest)

- `oax doctest [dir]`: the docstring examples are graded, not decorative —
  a stdlib-doctest runner walks every package module (and any plain `.py`
  directory, so probes are graded by the same loaders that grade the real
  tree); every module is reported (with or without examples — never faked
  green), a failing example rides its doctest log (Failed example /
  Expected / Got), an import failure folds with the real exception, one
  failure poisons the aggregate, the render is byte-deterministic with no
  wall-clock, the CLI exits 0 green / 1 failing; graded by golden task 40
  (12 checks, eval floor 39 → 40, matrix 40 tasks / 459 checks) and
  demonstrated by example 29; nine core modules gained curated `>>>`
  examples (redaction with the runtime-assembled fixture, events, jdiff,
  memory, cache, breaker, compact, mermaid, structured — 27 examples,
  floor pinned); the first run of the new drill caught two examples
  referencing a name their module never imported — fixed at the root;
  modules.md, the CLI table, the tutorial and the explainer page synced;
  manifest 145 files
- round two: eight more core modules carry curated `>>>` examples
  (llm, prompt, retry, jit, hooks, chain, snapshot, tools — 53 examples
  across 17 modules); the doctest drill's floor pins the grown set; the
  first run caught doctest's strict exception rule (user-defined
  exceptions are expected with their module path) and it was fixed at
  the root, never weakened
### Added — views (explain)

- `oax explain <NN-slug|path>`: the matrix explains itself from the CLI —
  one golden task's machine-readable spec (drill, task text, script
  turns, sorted expect keys, max_steps) joined with its prose explainer
  from `docs/explainers.md` in one byte-deterministic, wall-clock-free
  render; a spec without prose is reported loudly (naming the verify
  gate that forbids it), a missing spec raises, the CLI exits 0 found /
  1 missing; graded by golden task 39 (12 checks) — including the
  two-directional coverage cross-check — and demonstrated by example 28;
  modules.md, the CLI table, the tutorial and the explainer page
  synced. Round two: `oax explain --all` renders the whole matrix index
  in one deterministic render — sorted rows, honest `[NO-PROSE]` marks,
  an unreadable spec a loud error row, exit 1 while any task lacks
  prose; graded by two new explain-drill checks (matrix 40 tasks /
  462 checks) and demonstrated by example 28 step 8
  document it; matrix 39 tasks / 447 checks; manifest 144 files.

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
