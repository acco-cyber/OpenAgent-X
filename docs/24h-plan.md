# OpenAgent-X — 24-Hour SOTA Sprint Plan (Epoch 3)

> **History (recorded honestly)**:
> - **Epoch 1** (parts 1–53) was lost to a sandbox reset mid-sprint.
> - **Epoch 2** (parts 1–17: full foundation + golden matrix to 11 tasks /
>   98 checks) was lost the same way — it lived at `/home/z/OpenAgent-X`,
>   outside the durable volume, and was never pushed (origin needs absent
>   credentials).
> - **Epoch 3** rebuilds at the **durable path** `/home/z/my-project/OpenAgent-X`
>   (symlink `/home/z/OpenAgent-X` → there) so recycling can never wipe it again.
>   Part numbering restarts at 1 in the fresh repository.
> Origin push requires credentials that are currently absent — every slot
> pushes anyway: the GitHub REST API path (`scripts/push-via-api.py`) lands
> the backlog one commit at a time (blob → tree → commit → ref per commit,
> tree SHA verified, fast-forward only, never force-push) the moment a
> token appears in the environment or repo-root `.env`.

## Mission

Make OpenAgent-X the most auditable pure-stdlib agent framework on GitHub:
event-sourced truth, redaction by default, honest grading, offline-first
deterministic drills — then push *beyond* typical reference frameworks with
budgets, team handoffs, routing, JIT tool disclosure, layered prompts, memory,
snapshots, hash-chained traces, and a full developer ecosystem.

**Targets**: 250+ commits in 24h of slot time · eval count only moves forward ·
every commit contains real changes · 0 audit findings · every drill genuinely
green.

## Operating protocol (every slot MUST follow)

1. **Lock**: if `.slot-lock` exists and is younger than 25 min → abort ("busy").
   Else `date +%s > .slot-lock`; remove it at the end (always).
2. **State**: `git log --oneline -6`, `git status --short`, `git pull origin main`
   (tolerate failure), read this file, execute the **first `[ ]` slot**.
3. **Part numbering**: next part = (highest `— part N` in git log) + 1.
   Re-check right before committing; atomic commits end `— part N (a)`,
   `(b)` … and the slot's **final** commit ends `— part N`.
4. **Honesty rules**: pure stdlib only; drills must execute real behavior;
   harness errors fold into failing checks; fixtures are runtime-concatenated
   (`"ghp_" + "A1b2C3d4E5"*3 + "F9ab12"`-style) so `oax audit .` stays 0;
   never fake a green check; eval count never regresses.
5. **Verification gate** (all must pass before the final commit):
   - `node scripts/verify.mjs`
   - `python3 -m compileall -q openagentx examples`
   - `python3 -m openagentx doctor` (6/6)
   - `python3 -m openagentx audit .` → 0 findings
   - `python3 -m openagentx eval` → all green (count only grows)
   - `python3 -m openagentx examples` → all OK
   - staged diff secret grep → 0 matches
6. **Commit cadence**: 5–6 atomic commits per slot
   (feature → drills/golden task → docs → example → verify/chore → polish).
7. **Push**: `python3 scripts/push-via-api.py` first (GitHub REST API, one
   commit at a time, oldest first), then `sh scripts/push-one-by-one.sh` as
   git-transport fallback; on credential failure, record it and move on.
   Never force-push.
8. **Slot bookkeeping**: mark `[x]` in this file with evidence, commit as the
   final chore, remove `.slot-lock`, report slot/part/commits/verification.

## Slot matrix (Epoch 3)

### Phase 0 — Recovery foundation
- [x] S01-E3 part 1 — scaffold + core engine rebuild: events (dense append-only
  journal, torn-tail isolation), redaction engine, ScriptedLLM, sandboxed tools,
  event-sourced runner, team handoff runner, fallback router, views/replay
  (report/trace), honest eval harness + golden tasks 01–03 (26 checks),
  doctor + audit + CLI + verify.mjs + example 01 ✅ 3 tasks, 26 checks green
- [x] S02-E3 — golden tasks 04 `loop-budget` + 05 `stop-tool` + example 02 (redaction demo) ✅ 5 tasks, 46 checks green
- [x] S03-E3 — task 06 `redact-nested` + task 07 `audit-self` + example 03 (team handoff) ✅ 7 tasks, 66 checks green
- [x] S04-E3 — packs (deterministic manifest) + sbom (stdlib BOM) + tasks 08–09 ✅ 9 tasks, 86 checks green; `oax pack`/`oax sbom` live
- [x] S05-E3 — task 10 `team` + task 11 `router` golden tasks + README polish
  ✅ 11 tasks, 108 checks green; team drill now expect-driven (`brief_marker`,
  `specialist_reply_matches`, `handoff_count_matches`); README quickstart +
  runtime-guarantee sections live

### Phase 1 — Golden matrix expansion (eval 26 → ~120 checks)
- [x] S06-E3 — task 12 `memory-lite` (TF-IDF recall over past runs) + task 13 `compaction`
  ✅ 13 tasks, 131 checks green; `MemoryLite` + `oax recall`, `compact.py` +
  `oax compact` (tool pairs → `tool_fold`, torn sources refused); example 05
  live; examples count now five
- [x] S07-E3 — task 14 `cache` (prompt-hash response cache) + task 15 `hooks` (deny policy)
  ✅ 15 tasks, 152 checks green; `ResponseCache`/`CachedLLM` (exact-prompt
  hits, inner adapter saved, journals identical) + `HookPolicy` runner
  integration (every decision journaled as `hook`, denied calls never
  execute); example 06 live
- [x] S08-E3 — task 16 `parallel-fanout` + task 17 `structured-output` (JSON repair)
  ✅ 17 tasks, 177 checks green; `FanoutRunner` (N real branch agents on
  their own journals, failures recorded as data, structural determinism) +
  `structured.py` (`parse_json_loose` repair notes, `validate_schema` lite
  subset where True is never an integer); example 07 live
- [x] S09-E3 — task 18 `retry-backoff` + task 19 `circuit-breaker`
  ✅ 19 tasks, 201 checks green; `RetryLLM`/`BackoffPolicy` (deterministic
  exponential schedule, per-attempt log, loud give-up, retries invisible to
  the journal) + `CircuitBreaker` (trip surfaces the original fault,
  fast-fail without inner calls, tick-clock cooldown, probe closes or
  re-opens); example 08 live
- [x] S10-E3 — task 20 `planner-executor` + task 21 `snapshot-travel`
  ✅ 21 tasks, 227 checks green; `PlannerExecutor` (one planning turn
  fans out into real executor runs on `step-XX` journals, fenced plans
  repaired with notes + schema-validated, plan bugs stop `script_error`,
  failing steps are data) + `snapshot.py` (`snapshot_at`/`travel`: pure
  prefix folds, torn-tail/prefix isolation, loud bounds errors); example 09
  live
- [x] S11-E3 — task 22 `prompt-layers` (include order, cycles, substitution)
  ✅ 22 tasks, 240 checks green; `PromptLayers` (depth-first include
  expansion in declared order, include cycles reported with the full path,
  diamond includes expand per path, missing layers/variables name
  themselves, values stay literal so data never injects includes);
  example 10 live
- [x] S12-E3 — task 23 `tools-jit` (JIT tool disclosure)
  ✅ 23 tasks, 254 checks green; `JITDisclosure` + `JITAgentRunner`
  (turn-zero visibility journaled, undisclosed calls refused before hooks
  with one `tool_hidden` event and zero side effects, `tools_expand`
  control-plane disclosure lands as an ordinary journaled call, keyword
  rules with deterministic sorted cap that never hides the control plane,
  every visibility change journaled as `tool_disclose` with the full set
  and the additions, re-runs event-for-event identical); example 11 live
- [x] S13-E3 — task 24 `chaos` (combined faults in one run) + task 25 `hash-chain`
  ✅ 25 tasks, 282 checks green; `ChaosLLM`/`ChaosTools` (combined faults in
  ONE run on a deterministic plan, every injection ledgered, faulted tool
  calls never execute — zero side effects, recovery via RetryLLM with scars,
  re-runs identical) + `chain.py` (ChainedJournal commits chain {prev,
  digest} per line invisible to old readers, verify_journal localizes
  edited/deleted/reordered lines, torn tails isolate unsealable, plain
  journals verify chained:false, seal refuses what it cannot verify);
  example 12 live

### Phase 2 — Power tooling & hardening
- [x] S14-E3 — `oax diff` (event-level journal diff) + `oax stats` (run analytics)
  ✅ 27 tasks, 306 checks green; `jdiff.py` (semantic projection ignores
  wall-clock ts, strict mode compares every stored byte, longest common
  prefix names diverged_at, removed/added tails carry real payloads, torn
  tails isolate per side, byte-deterministic render, `oax diff` exits 0
  same / 1 different) + `stats.py` (fingerprint takes every counter from
  replay() itself so the two views never disagree, adds per-type counts,
  per-tool call/ok/fail pairing, torn/density flags and the wall-clock
  span reported but never graded); example 13 live; examples count now
  thirteen
- [x] S15-E3 — `oax bench` (journal throughput microbench) + fuzz harness (seeded)
  ✅ 29 tasks, 330 checks green; `bench.py` (deterministic synthetic
  workload through a real Journal, three timed phases reported as honest
  single-run wall-clock that is never graded, zero-event bench at 0.0
  rates) + `fuzz.py` (seeded attack schedule: torn-tail garbage every 7th
  op isolates + truncates to a dense resume, middle-tear splice every 11th
  op raises and restores byte-identically, unicode payloads round-trip,
  two reads fold to one replay state, no timings so the same seed always
  yields the same verdict); `oax bench` / `oax fuzz` exit-code contracts
  live; example 14 live; examples count now fourteen
- [x] S16-E3 — property suite (torn-tail/replay/density under random traces)
  ✅ 30 tasks, 342 checks green; `property.py` (a seeded lottery picks each
  step — append / torn-tail injection / writer restart — and after EVERY
  step the journal is re-read from disk: density exactly 0..n-1, every
  injected tear isolated AND strictly refused AND truncation-restored to
  the exact pre-tear bytes, the round-trip matching the written plan,
  two independent reads folding to one state, and every `ts` on disk
  rewritten to a different wall-clock folding to the identical replay
  state with the semantic diff calling the shifted journal the same —
  replay is a function of events, never of the clock); reports carry no
  timings so the same seed always yields the same verdict; `oax property`
  exit-code contract live; example 15 live; examples count now fifteen
- [x] S17-E3 — pack v2 (signed manifest) + sbom v2 (dependency graph)
  ✅ 32 tasks, 366 checks green; `pack2.py` (HMAC-SHA256 over the canonical
  sig-stripped manifest bytes, key_id names the key without revealing it,
  constant-time verify, wrong key / edited entry / tampered file each fail
  their own named layer while both layers always report, v1 still reads
  the core) + `depgraph.py` (every local import resolves to an in-package
  edge with a kind: eager edges build the longest-path layers and Tarjan
  cycle detection, lazy function-body edges are reported as data — the
  CLI's real cli/doctor/evaluation/sbom deferral ring is named out loud
  without tainting the eager layering; entries/leaves/orphans/fan sums
  derived, sorted, timestamp-free); `oax pack2` / `oax graph` exit-code
  contracts live; example 16 live; examples count now sixteen
- [x] S18-E3 — report v2 (dashboard HTML) + mermaid trace export
  ✅ 34 tasks, 389 checks green; `dashboard.py` (counters taken from
  run_stats — which takes replay's — so dashboard/stats/replay never
  disagree; integrity strip with dense/torn flags and duration reported
  not graded, summary cards, per-type bars derived from integer counts,
  per-tool table, redacted+escaped timeline; inline CSS, zero external
  assets, no timestamps; same file in -> byte-identical HTML/JSON out)
  + `mermaid.py` (one zero-padded node per event with quote-escaped,
  newline-stripped truncated labels, one spine edge per consecutive
  pair, deterministic call/fail/err/say classing, extension event types
  through the generic path, honest empty state, torn tails diagram the
  dense prefix only); a runtime-assembled raw token hand-written into a
  journal is re-redacted by BOTH views (defense in depth); `oax
  dashboard` / `oax mermaid` exit-code contracts live (0 rendered /
  1 missing); example 17 live; examples count now seventeen
- [x] S19-E3 — examples gallery (budget guard, cache, hooks, replay diff)
  ✅ 35 tasks, 399 checks green; four deep-dive gallery examples, one per
  theme, each failing loud: `18_budget_guard.py` (governor stops BEFORE the
  rejected call — budget event names the refused tool with used/cap, cap
  recorded at run_start, executed calls are exactly the pre-budget prefix,
  the rejected write leaves zero side effects while the allowed one
  persists, no reply fabricated, the capped attempt counts as a step, the
  scripted tail stays unconsumed, reply/max_steps/budget proven to be
  three distinct stop reasons, re-run diffs SAME) · `19_cache_hits.py`
  (one script twice through a shared ResponseCache: all misses then all
  hits with the inner adapter called 0x — observable proof — journals
  diff SAME because the cache sits at the LLM layer, key content/order
  sensitivity, mutation and empty-store honesty) · `20_hooks_deny.py`
  (every decision journaled as a hook event incl. allows, deny carries
  its named reason, the refused call leaves zero side effects, the loop
  adapts, the denied turn still counts as a step, snapshot tamper-proof,
  first-match wildcard rules) · `21_replay_diff.py` (two real runs SAME
  with ts ignored, one drifted argument diverges at the derived calc seq
  with both payloads named, a single edited ts semantic-SAME but
  strict-DIFFERENT, torn tail isolates per side, self-diff identity,
  CLI 0 same / 1 different); golden task 35 grades the budget story
  end-to-end (+10 checks); README gains the Examples-gallery table;
  examples count now twenty-one

### Phase 3 — Docs & ecosystem
- [x] S20-E3 — docs: module guides + tutorial 0→hero
  ✅ 35 tasks, 399 checks green; `docs/modules.md` guides all 39 modules
  grouped by job (core loop, views and analytics, reliability,
  orchestration, integrity and supply chain, meta) with real entry points
  and per-module invariants; `docs/tutorial.md` walks zero-to-hero in ten
  steps (purity gate → first run → journal-as-truth → the four stop
  reasons → redaction → cache/hooks → resilience → orchestration →
  verification stack → ship → hero capstone: write and grade your own
  drill) with every python and sh snippet executed green before commit;
  README + ai-context cross-link both; `verify.mjs` gains a docs-sync gate
  (every module guided, tutorial names only real subcommands and existing
  examples); required-files manifest carries both docs
- [x] S21-E3 — docs: ADR pack (10 records) + glossary + FAQ
  ✅ 35 tasks, 399 checks green; `docs/adr/` holds ten records
  (journal-is-the-truth, stdlib-only-offline, redaction defense in depth,
  scripted adapters, honest golden drills, four stop reasons +
  control-plane, views-from-replay determinism, opt-in hash chains,
  supply-chain proofs in three layers, docs-that-cannot-drift), each with
  Status/Context/Decision and honest costs, indexed by the adr README;
  `docs/glossary.md` defines thirty terms grounded in their owning
  modules; `docs/faq.md` answers fourteen real questions (budget stops,
  invisible retries, strict vs semantic diff, True-is-not-an-integer,
  torn tails vs middle tears, what is not graded against a real model);
  verify.mjs gains the ADR gate (>=10 records, all four sections, all
  indexed) and the manifest names every ADR, the glossary, and the FAQ
- [x] S22-E3 — README overhaul (SOTA presentation, badges, demo traces)
  ✅ 35 tasks, 399 checks green; README rebuilt as a SOTA front door: honest
  badges (python 3.10+, zero dependencies, eval 35 tasks / 399 checks, secret
  audit 0 findings, offline-first, MIT) each linked to its proof; a demo
  traces section showing one real run three ways — the `oax run` console
  session, the 12-event journal pasted verbatim from disk (the fixture token
  visible only as `[REDACTED:github_token]` with the redaction count
  recorded), and the deterministic `oax mermaid` diagram; an architecture
  mermaid (adapter → runner → layered guards → registry → redaction boundary
  → journal → replay → views, refusals journaled as data); an honest generic
  comparison table; a documentation map; gallery rows carry real `examples/`
  paths; quickstart promoted to the top; `verify.mjs` gains the README-sync
  gate (subcommands/examples/docs references must resolve; eval-scale claims
  must equal the golden-task count)
- [x] S23-E3 — CI: GitHub Actions (verify/compileall/eval/audit) + community files
  ✅ 35 tasks, 399 checks green; `.github/workflows/ci.yml` runs the seven
  local gates on a Python 3.10 + 3.12 matrix with ZERO install steps (pure
  stdlib: checkout + interpreters is the whole environment), no secrets,
  least-privilege `contents: read`, manual dispatch included; community files
  live (CONTRIBUTING.md with the seven-gate contract and purity rules,
  CODE_OF_CONDUCT.md, SECURITY.md routing to private vulnerability reporting
  with the project-specific vulnerability classes, bug-report template that
  demands the journal excerpt); README wears the real workflow badge + a CI
  section; FAQ #15 explains why zero-dependency CI has nothing to install;
  verify.mjs gains the CI-sync gate (every gate command present, no
  `pip install`, no `secrets.`, 3.10 floor pinned, badge workflow must
  exist); manifest carries ci.yml + all community files
- [x] S24-E3 — eval parallelism + perf pass + CHANGELOG + 1.0.0-rc1
  ✅ 35 tasks, 399 checks green; `oax eval --workers N` runs drills on a
  stdlib thread pool with verdicts proven identical to the serial run
  (order, pass counts, verdicts; parallelism changes the wall-clock, never
  the grade) and per-task wall-clock on every line, reported never graded;
  honest finding recorded: GIL-bound drills make 4 workers slower than
  serial (1.77s vs 1.37s pre-optimization); perf pass profiled the matrix
  and removed the real hot spot — build_depgraph re-parsed every module
  after build_sbom had already parsed it, now one read + one parse feeds
  both (graph_sha256 unchanged, BOM delta confined to the two edited
  sources, proven against HEAD; eval median 1.349s → 1.247s serial,
  1.772s → 1.569s at 4 workers); CHANGELOG.md records the Epoch 3 rebuild
  for 1.0.0-rc1 with the deliberate costs pointed at their ADRs;
  __version__ 0.1.0 → 1.0.0-rc1; example 22 proves the parallel-identity
  contract end-to-end; README counts twenty-two demos and names the
  release candidate; manifest carries CHANGELOG.md + example 22

### Phase 4 — Release
- [x] S25-E3 — final regression sweep + release 1.0.0 + retrospective
  ✅ 36 tasks, 411 checks green; the release-sweep drill (golden task 36,
  12 checks) re-demands the core invariants on one real run: counters one
  source of truth, views byte-identical, self-diff the zero diff, raw
  runtime tokens re-redacted by both views, chained journals seal, repo
  audits 0, doctor 6/6, and `__version__` must equal the top CHANGELOG
  entry (enforced release-metadata sync); `__version__` 1.0.0-rc1 → 1.0.0
  with the CHANGELOG 1.0.0 entry recording the release engineering
  honestly; example 23 performs the sweep's story (and example 22's
  matrix assert moved to a grow-only floor of 36);
  `docs/retrospective.md` reviews the sprint with every number gated;
  README badge/counts 36 tasks / 411 checks, gallery and documentation
  map rows live; eval floor 35 → 36 in verify.mjs; manifest 131 files

If slots run out before 250 commits, continue with stretch slots (S26-E3+):
per-drill explainers, `oax replay --from`, `oax grep`, more examples — never
pad with empty commits.

### Phase 5 — Stretch

- [x] S26-E3 — `oax grep`: the journal is searchable truth, not just
  replayable truth
  ✅ 37 tasks, 423 checks green; `grep.py` filters one journal's events
  with plain deterministic matchers all AND-ed (case-sensitive substring
  over the type+payload JSON projection, exact event type, exact payload
  tool name covering call+result pairs, a `since_seq` floor, a `limit`
  cap in seq order); every match renders through the redaction engine —
  raw secrets live on disk, so a verbatim search view would be a leak
  channel, and grep proves the harder case: searching FOR the raw token
  matches on disk and still prints only `[REDACTED:github_token]`; torn
  tails isolated and never searched, honest empty result, no timestamps,
  CLI 0 matched / 1 none / 1 missing with redacted stdout; golden task 37
  (12 checks) + example 24 + module guide + CLI-table row + tutorial
  Step-8 line + FAQ #16; CHANGELOG gains an [Unreleased] section and the
  version/changelog sync gate now skips non-version headers (both the
  sweep drill and example 23 fixed at the root); eval floor 36 → 37;
  manifest 134 files; task 37's write_file now uses the real signature
  (path+text) so its expectations are truly observed

- [x] S27-E3 — `oax replay --from`: the journal folds from the middle,
  honestly

- [x] S28-E3 — presentation pass: the README grows a real banner, a
  real-session demo video, and a developer-value map
  ✅ assets recorded from a real session against a clean clone: banner
  rendered programmatically (no AI text), demo.gif 1.1 MB + demo.mp4
  787 KB — clone → doctor 6/6 → eval 38 tasks 435/435 green → run
  --timeline with live redaction at the boundary → stats → grep, every
  visible line is the tool's real stdout; README gains a navigation
  table, the Watch-it-run section, Why-developers-use-it (six concrete
  ways the repo helps working engineers), a Contributing section with
  the enforced rules, and the full clone URL (placeholder removed); the
  stale 35-golden-drills claim in the comparison table trued up to 38;
  binary assets manifest-tracked (140 required files), audit 0 findings
  (binaries scanned clean), doctor 6/6, verify OK, eval 38/435 green
  ✅ 38 tasks, 435 checks green; `replay.py` folds every event with
  `seq >= N` from zero at that point — bounds honest (0..max seq, an
  empty journal exposes only the zero state at 0, out-of-bounds raises
  ValueError, never silently clamped), density required (a gapped
  journal raises, never folds), additivity claimed only where true
  (11 monotone counters == whole − prefix) and never where false
  (clamped runs_open; window-local last_reply/final_stop), from max
  seq folds exactly one event, torn tails invisible + reported, the
  state view renders through the redaction engine — a runtime-assembled
  raw token on disk never leaves it even inside last_reply; the render
  names its window, byte-deterministic, no timestamps; CLI 0 folded /
  1 missing / 2 bad bounds with redacted stdout; golden task 38
  (12 checks) + example 25 + module guide + CLI-table row + tutorial
  verification-stack line + FAQ #17 + CHANGELOG [Unreleased] entry;
  eval floor 37 → 38; manifest 137 files

- [x] S29-E3 — per-drill explainers: every golden task gets its prose —
  what the run does, what the checks grade, how it fails loudly — with a
  verify gate so the prose cannot drift from the matrix
  ✅ `docs/explainers.md` walks all 38 golden tasks in the modules.md
  lens (ten theme groups, three honest lines each: the run / the checks
  grade with real check counts / loud failure), stems cross-checked
  against `golden_tasks/` (38/38, zero unknown headings); verify.mjs
  gate 8 welds the page to the matrix both directions (probe: typoed
  heading → `EXPLAINERS MISSING` + `names unknown task`, exit 1,
  restored green); README doc-map row + tutorial Step-10 link;
  manifest 140 → 141; eval 38 tasks / 435 checks unchanged (docs-only
  slot, count cannot regress), audit 0, doctor 6/6

- [x] S30-E3 — more examples: the gallery grows the two demos the
  stretch list still owes — grade-your-own-drill (the hero capstone as
  runnable code) and the flight-recorder tour (one run through every
  view)
  ✅ example 26 (`26_author_your_own_drill.py`): spec authored, real run
  graded via run_golden_task (9/9 green, check names printed), honesty
  probed three ways — wrong expect → `reply_text_matches` red,
  malformed script line → `harness_error` fold (real exception detail),
  unknown drill → `unknown_drill` — then repaired to green; example 27
  (`27_views_tour.py`): 16-event run through timeline/report/stats/
  grep/self-diff/replay-from/dashboard/mermaid, all re-renders
  byte-identical, counters from one replay fold, bounds loud, tour-wide
  leak sweep green; README quickstart 25→27 + two gallery rows,
  tutorial Step-10 capstone link, CHANGELOG [Unreleased] entry,
  manifest 141 → 143; examples suite all OK, eval 38/435 unchanged,
  audit 0, doctor 6/6

- [x] S31-E3 — `oax explain`: the matrix explains itself from the CLI —
  one task's spec and its prose joined, deterministic render, honest
  when prose is missing, graded by a new drill (task 39)
  ✅ `explain.py` (explain_task / load_explainers / render_explain) +
  CLI subcommand (0 found / 1 missing, id or path form) + modules.md
  section; drill explain grades 12 checks — real-task explain, fields
  vs the JSON read independently, sorted expect keys, both-halves
  render, byte-determinism, no wall-clock, two-directional prose
  coverage cross-check, loud no-prose ghost, missing-spec raises, CLI
  contract; task 39 lands with its explainers entry (gate 8 satisfied
  same-commit), eval floor 38 → 39, matrix 39 tasks / 447 checks green;
  README badge/inline/CLI-table/comparison synced (demo alt text stays
  38 — it describes the recording), tutorial counts 39, example 28 +
  manifest 144, CHANGELOG [Unreleased] entry; audit 0, doctor 6/6

- [x] S32-E3 — docstring self-checks: the examples are graded, not
  decorative — a stdlib-doctest runner over every package module
  (`oax doctest`), curated `>>>` examples on the core modules
  (redaction, events, jdiff, memory, cache, breaker, compact, mermaid,
  structured), loud edges (poisoned docstring → expected/got, import
  bomb → folded real exception, one failure poisons the aggregate), and
  a new drill grading it all (task 40)
  ✅ `doctests.py` (load_package_modules / load_file_modules feeding one
  grading path, run_doctests / render_doctests) + CLI `oax doctest [dir]`
  (exit 0 green / 1 failing, probed both ways) + modules.md section;
  nine core modules gained curated `>>>` examples (27 examples, floor
  pinned by the drill) — the first run caught two examples referencing a
  name their module never imported (jdiff, mermaid), fixed at the root
  rather than weakened; drill doctest grades 12 checks — real tree green
  with the 27/9 floor pinned, every module reported sorted with none
  skipped, no-example modules counted honestly (33 counted, never faked
  green), poisoned docstring loud (promised 6, computed 5) with the
  Failed example / Expected / Got log, import bomb folded with the real
  RuntimeError, the redaction example really graded on its
  runtime-assembled fixture, byte-deterministic render, no wall-clock,
  one failure poisons the aggregate, CLI 0 green / 1 failing; task 40
  lands with its explainers entry same-commit (gate 8 satisfied), eval
  floor 39 → 40, matrix 40 tasks / 459 checks green; README
  badge/inline/comparison/CLI-table synced + gallery row + quickstart
  twenty-nine demos, tutorial snippet + capstone line, golden-table row
  40 + no-script shape note, example 29 + manifest 146, CHANGELOG
  [Unreleased] entry; audit 0, doctor 6/6

- [x] S33-E3 — doctests round two: the second ring — curated `>>>`
  examples reach eight more core modules (llm, prompt, retry, jit,
  hooks, chain, snapshot, tools), the drill floor pins the grown set,
  the CLI gains floor flags so operators demand the same bar, task 40
  grades it all
  ✅ 26 new examples land on llm (scripted turns + loud qualified
  exhaustion), prompt (include-then-substitute, missing-var and cycle
  raise with the path), retry (plain-math schedule), jit (frozen rule
  repr, control tool), hooks (first-match wins, wildcard, empty
  allows), chain (genesis 64 zeros, empty head), snapshot (one open
  run, ZERO_STATE equality), tools (static sorted registry) — 53
  examples / 17 modules, drill floor pinned 9/27 -> 17/53; first-run
  catches fixed at the root: doctest qualifies user-defined exceptions
  with their module path (llm's ScriptExhausted expected in full), one
  announce landed a commit late with a correction note; floor flags
  --min-modules/--min-examples make the bar operator-grade (drill grows
  to 13 checks, matrix 40 tasks / 460 checks); the slot also caught and
  fixed a real latent eval flake at the root — the doctest engine's
  process-global sys.stdout swap raced the parallel pool (explain lost
  captured lines, doctests saw foreign prints; 3/16 loops red) — the
  engine now grades in a fresh child interpreter and the five
  redirecting drills hold CLI_STDOUT_LOCK; proof 0 failures in 30 full
  matrix runs across both modes + 6/6 examples suites; README gallery
  row corrected in this commit (the (d) message claimed it a commit
  early — no history rewritten); audit 0, doctor 6/6

- [x] S34-E3 — the matrix index: `oax explain --all` — every task's
  prose coverage in one deterministic render (sorted rows, honest
  no-prose marks, exit 1 while any task lacks prose), graded by two new
  explain-drill checks and demonstrated by example 28
  ✅ the slot opened with a plan-truth repair (S33-E3's checkbox read
  [ ] at HEAD while its final commit recorded [x], evidence duplicated —
  flipped and deduped, claims re-verified against the live tree before
  the edit); explain_all() + render_explain_index: 40 rows in matrix
  order, [NO-PROSE] ghosts and unreadable-spec error rows loud, ok
  False while any prose missing, render byte-deterministic with no
  wall-clock; CLI --all (exit 0 covered / 1 prose missing, task arg now
  optional); explain drill grows to 14 checks (index_covers_matrix,
  index_deterministic_cli_ghost with the CLI capture under
  CLI_STDOUT_LOCK), matrix 40 tasks / 462 checks; README
  badge/inline/quickstart/CLI-row, explainers intro + task-39 prose
  (14) with the index contract, golden row 39 (14), tutorial capstone
  line, example 28 step 8, modules.md invariant, CHANGELOG round-two
  bullet; the 462 cascade split across two commits after a line-wrapped
  anchor missed — recorded in the completion commit; audit 0, doctor
  6/6 (truth repair, next slot: this checkbox read [ ] at HEAD while
  its own final commit 857d4d4 recorded [x] — the flip is applied now,
  claims re-verified against the live tree before the edit: verify OK,
  doctor 6/6, audit 0, eval 40 tasks / 462 checks green; no history
  rewritten, the correction is the commit)

- [x] S35-E3 — the release attestation: `oax attest` — one command, one
  artifact, every gate: doctor (purity + integrity), audit (0
  findings), doctests (docstring examples green), manifest (the tree
  hashes deterministically twice) and the matrix (specs + prose
  coverage) aggregated into one byte-deterministic verdict — human
  render counters-only, machine JSON carries the tree hash; a gate that
  crashes is a red gate carrying the real exception, a planted secret
  turns the verdict red, exit 0 green / 1 any gate red; graded by a new
  drill (task 41) in a child interpreter and demonstrated by example 30
  ✅ attest.py (collect_gates / aggregate / render / artifact_json, five
  gates in fixed order) + CLI `oax attest [root] [--json PATH]` (exit 0
  green / 1 any red, both probed); a crashing gate folds red with the
  real exception (IsADirectoryError probe), an empty gate list is never
  green, the render is counters-only (no hash, no path, no wall-clock,
  byte-identical twice) while the sort_keys artifact carries root + the
  64-hex tree hash; gates root-parametric (package-mode doctest imports
  when the root is the running package, bare-file mode otherwise, no
  package = loud red); attest.py carries six curated `>>>` examples
  (doctest floor 18 modules / 59 examples); the drill's first run
  caught the import bomb's real exception never reaching the gate
  detail (counts only) — root-fixed: failing gates now carry each
  failure's first log line; drill attest grades 12 checks in a fresh
  child interpreter (the doctest drill's stdout discipline, inherited):
  real tree green, doctest floor pinned 53/17, matrix gate covers
  prose + 137 expect keys, manifest hash matches an independent build,
  synthetic tree green, import bomb loud, planted secret red with the
  file named and the secret never echoed, crash fold, render +
  artifact determinism, CLI contract; task 41 lands with its
  explainers entry same-commit (gate 8 satisfied), eval floor 40 → 41,
  matrix 41 tasks / 474 checks green; README badge/inline/eval-line/
  quickstart/CLI-table/comparison/doc-map, tutorial capstone +
  snippet, CHANGELOG release-attestation section, modules.md attest
  section, golden row 41 + no-script shape note, example 30 + manifest
  148; the README count gate rode red for exactly one commit ((c)
  landed the matrix growth before the prose cascade — recorded in the
  (d) message, verify green again there); audit 0, doctor 6/6

- [x] S36-E3 — the multi-run index: `oax runs [dir]` — a directory of
  journals becomes one deterministic table (rows sorted by file name,
  torn tails flagged but never filtered, middle-torn journals loud error
  rows carrying the real exception, totals additive only where true,
  counters never payloads), graded by a new drill (task 42) and
  demonstrated by example 31
  ✅ `runs.py` (index_runs / totals_of / render_runs / artifact_json) +
  CLI `oax runs [dir]` (exit 0 indexed / 1 nothing to index, probed both
  ways plus missing-dir) + modules.md runs section; every row's counters
  come from the same run_stats the single-journal view uses (one grading
  path — the index can never disagree with `oax stats`); the smoke probe
  caught the folded TornMiddleError carrying the full temp path into the
  render — root-fixed: the real exception text with the redundant
  directory prefix stripped, folded not hidden; torn tails are flags
  (intact prefix counts, row says torn), a middle-torn journal is a loud
  error row, additivity claimed only where true (events + tool counters
  sum, durations never — spans overlap), zero journals honest emptiness
  (ok False); nine docstring examples on runs.py graded by the doctest
  engine (floor 19 modules / 68 examples); drill runs grades 12 checks
  in a fresh temp workspace of four canonical-Event journals (clean,
  torn-tail, middle-torn, payload-secret) — rows_sorted_deterministic,
  counters_match_stats, totals_additive_where_true (the drill's first
  run caught its own assertion saying 11 events where the real sum was
  10 — corrected against the sum, never against a wish),
  torn_tail_flagged_not_filtered, middle_torn_loud_error_row,
  no_payload_leak, empty_dir_loud, non_jsonl_ignored,
  artifact_deterministic (byte-identical twice, sort_keys, no directory
  path), render_no_wall_clock, missing_dir_raises, cli_exit_contract;
  task 42 lands with its explainers entry same-commit (gate 8
  satisfied), eval floor 41 → 42, matrix 42 tasks / 486 checks green;
  README badge/inline/eval-line/CLI-glance/comparison/module-count 44,
  tutorial verification-stack line + one-grading-path paragraph,
  CHANGELOG multi-run index section, golden row 42 + Current line +
  no-script shape note, example 31 + manifest 151; commit (d)'s subject
  lost its part suffix — recorded here, no history rewritten; audit 0,
  doctor 6/6

- [x] S37-E3 — the auditor audits itself: golden task 43 grades the
  doctor's gates at their failure edges — a planted third-party import
  caught by name, a network import caught, a missing required file
  named, a malformed spec folded loudly, an unknown drill named, gates
  proven independent in one poisoned tree, the render byte-deterministic
  with no wall-clock, the CLI's 0/1 contract probed both ways — every
  probe in a fresh temp workspace, plus the render_doctor extraction
  the drill grades
  ✅ render_doctor extracted from the CLI into doctor.py as a pure
  function of the gate list (byte-identical output, docstring examples
  graded — floor 20 modules / 71 examples; the first run caught the
  expected FAIL line one space short, fixed at the root); drill doctor
  grades 12 checks in fresh temp workspaces — real tree 6/6, render
  deterministic + no wall-clock, clean synthetic workspace green,
  foreign.py:numpy caught by stdlib_purity, netty.py:socket by
  offline_purity, gone.txt named, truncated bad.json folded with the
  real exception, ghost.json named, one poisoned tree turns exactly the
  four planted gates red (the drill's first run caught sys missing from
  evaluation's imports — root-fixed), CLI 0 green / 1 red both probed;
  task 43 lands with its explainers entry same-commit (gate 8
  satisfied), eval floor 42 → 43, matrix 43 tasks / 498 checks green;
  README badge/inline/eval-line/CLI-glance + gallery row 32 + thirty-two
  demos, modules.md doctor section (render + failure-edge contract),
  tutorial doctor line + stale 41-tasks comment corrected to 43, golden
  row 43 + Current line, CHANGELOG section, example 32 + manifest 153;
  README counts rode red for exactly one commit ((b) landed the matrix
  growth before the docs cascade — recorded in the (b) message); audit
  0, doctor 6/6

- [x] S38-E3 — tamper evidence from the CLI: `oax chain <journal>`
  verifies the hash chain (exit 0 intact / 1 broken, torn or missing,
  the break index named) and `--seal` prints the 64-hex head of a fully
  intact chain-written journal (exit 1 unsealable with the reason
  named), graded by a new drill (task 44) that tampers with real
  journals in fresh temp workspaces — edits, deletions and reorders
  localized, seal refusals loud, plain journals honest
  ✅ `_cmd_chain` + parser: verify mode prints chain_report's
  deterministic one-line verdict, exit 0 intact / 1 broken-torn-missing
  (a torn tail is an incomplete file — the intact prefix still reports
  ok but the CLI refuses exit 0 with the `+torn_tail` mark named;
  read_events_safe would otherwise bless an absent file as ok — the CLI
  names the missing path); --seal prints exactly seal()'s 64-hex head,
  every ChainError refusal (torn, broken, empty, not chain-written) a
  named one-line rejection, never a traceback; chain_report grew an
  optional precomputed report (verify once, render once); drill
  chain_cli grades 12 checks on real journal copies in a fresh temp
  workspace — the fixture written by the module's own line writer over
  fixed canonical Events (deterministic head, no 10-digit-run flake in
  the render), stored head == independent recomputation, genesis on
  disk, CLI render byte-identical to the module's, edited payload byte
  localized at index 1, deleted line at its first mislink, reordered
  pair at index 0, torn-tail exit contract, seal matches head, three
  refusals named, plain honest, missing named, no wall-clock; task 44
  lands with its explainers entry same-commit (gate 8 satisfied), eval
  floor 43 → 44, matrix 44 tasks / 510 checks green; README
  badge/inline/eval-line/CLI-glance + gallery row 33 + thirty-three
  demos, modules.md chain section (chain_report + operator contract +
  task-44 grading), tutorial verification-stack chain line, golden row
  44 + Current line, CHANGELOG section naming the blessing-hole closed,
  example 33 + manifest 155; audit 0, doctor 6/6

- [x] S39-E3 — redaction species round three: the boundary learns six
  more high-confidence credential shapes (Google `AIza…` API keys,
  GitLab personal access tokens, Stripe live/test secret keys, npm
  tokens, JSON web tokens, PEM private key blocks) and every consumer
  of the pattern table hardens at once — the runner's journal writes,
  every view that re-redacts, `oax grep`'s rendered matches and
  `oax audit`'s findings — graded by a new drill (task 45) at the
  failure edges: each species caught, near-misses (a short AIza tail,
  a 19-char GitLab token, a 15-char Stripe body, a 35-char npm token,
  a JWT missing its signature, a CERTIFICATE block) left alone, the
  five legacy species still caught, a planted tree found kind-by-kind
  with every snippet redacted, and the repo itself still 0 findings
  ✅ PATTERNS grows the six round-three species (google_api_key with a
  35-char tail where length is the confidence, gitlab_pat, stripe_secret
  live+test, npm_token, jwt with the signature segment required so
  alg=none headers stay prose, private_key_block covering RSA/OPENSSH/
  PGP BLOCK) and every consumer hardened at once — audit.py, the
  runner's journal boundary, every re-redacting view and oax grep all
  walk the same table, zero new code paths; vault_value grows the six
  runtime-concatenated fixture keys so the repo still audits to 0
  findings; a google_api_key docstring example joins the graded
  doctests; drill species grades 13 checks in fresh temp workspaces —
  each species caught kind-by-kind, Stripe test mode, all three private
  key variants, six near-misses left alone (short tails, unsigned JWT,
  CERTIFICATE block), the five legacy species still caught, a mixed
  line reporting exactly three redactions, the planted tree found with
  snippets redacted and two scans byte-identical, the repo itself 0
  findings, the grep render redacted and byte-identical twice with no
  wall-clock, the table pinned at eleven species; task 45 lands with
  its explainers entry same-commit (gate 8 satisfied), eval floor
  44 → 45, matrix 45 tasks / 523 checks green; README
  badge/inline/eval-line + gallery row 34 + thirty-four demos,
  modules.md redact + audit sections (one-table-many-consumers +
  near-miss contract), tutorial secrets step round-three paragraph,
  golden row 45 + Current line, CHANGELOG species section, example 34
  + manifest 157; verify rode red for exactly one commit ((c)
  referenced example 34 one commit before (d) landed it — recorded in
  the (c) message); audit 0, doctor 6/6

- [x] S40-E3 — the matrix becomes addressable: `oax eval --list` prints
  the honest inventory (id + drill rows sorted, the count named, exit 1
  on emptiness) and `--only <names>` runs a named subset instead of all
  45 drills — every name matches a task id exactly or a drill name (a
  drill shared by several tasks selects all of them), duplicates dedupe,
  unknown names are rejected loudly before anything runs (a subset you
  can't name is not a subset; silently running the rest would bless the
  typo); the selection shares run_selected with the full run (one
  grading path — a subset grades identically to the corresponding slice
  of the full run) and the exit contract is unchanged (0 green / 1 any
  red); graded by a new drill (task 46) on the real matrix and on a
  poisoned temp matrix — red tasks named, unknown named, empty names
  named
  ✅ _cmd_eval rebuilt over resolve_only / run_selected / task_brief in
  evaluation.py: --list prints the honest inventory (rows in task
  order, count named, exit 1 on missing/empty dir) and composes with
  --only; --only resolves task ids and drill names (budget's two tasks
  prove the drill-name semantics), dedupes, and rejects unknown and
  blank names loudly before anything runs — no task lines, no summary,
  no traceback; run_eval's timed core factored into run_selected so
  full and subset runs share one grading path while run_eval keeps its
  two-tuple contract; the summary line names the selection (only=…);
  drill eval_only grades 14 checks — inventory complete/sorted/
  counted/byte-identical twice, composition, single green subset, two
  reports in task order, id==drill-name resolution (wall-clock column
  normalized away — the first live comparison flaked on seconds and
  was root-fixed), dedupe, unknown/blank named, poisoned temp matrix
  red named with unknown_drill, mixed subset honest, one-grading-path
  proof, empty dir honest; task 46 lands with its explainers entry
  same-commit (gate 8 satisfied), eval floor 45 → 46, matrix 46 tasks
  / 537 checks green; README badge/inline/eval-line + CLI-glance
  --only/--list rows + gallery row 35 + thirty-five demos, modules.md
  evaluation section (resolve_only/run_selected + reject-don't-skip),
  tutorial hero step addressable-matrix paragraph, golden row 46 +
  Current line, CHANGELOG eval-only section, example 35 + manifest
  159; verify rode red for exactly one commit ((c) referenced example
  35 one commit before (d) landed it — recorded in the (c) message);
  audit 0, doctor 6/6

- [ ] S41-E3 (stretch, announced at slot open): the HYDRION ONE blueprint
  lands as design input and the README reaches dev-star grade — the
  36-page product/research/engineering blueprint (v1.0, 2026-11-05) is
  ported in full into docs/blueprint/ (six files: index + product +
  architecture + platform + delivery + evidence; claims discipline
  preserved — a proposed plan, never a claim of implemented capability),
  and its §5 durable task lifecycle becomes real checked code:
  openagentx/lifecycle.py (eleven canonical states, frozen terminals,
  approval bound to the exact plan hash, append-only journal events with
  redacted reasons, replay rebuilds byte-identical), graded by task 47
  (drill lifecycle, 13 checks) and walked end-to-end by example 36; the
  README grows the blueprint section, the lifecycle guarantee, a drill
  catalog and honest re-counts (47 tasks / 550 checks, 36 demos, 45
  modules); the slot opens by adopting an orphaned working-tree fix that
  part 40's final commit message claimed but never committed (the
  id-vs-drill comparison normalized its wall-clock column — a live flake
  upstream, verified green before adoption)
