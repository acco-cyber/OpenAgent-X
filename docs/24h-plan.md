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

- [ ] S33-E3 — doctests round two: the second ring — curated `>>>`
  examples reach eight more core modules (llm, prompt, retry, jit,
  hooks, chain, snapshot, tools), the drill floor pins the grown set,
  the CLI gains floor flags so operators demand the same bar, task 40
  grades it all
  ✅ 26 new examples land on llm (scripted turns + loud qualified
  exhaustion), prompt (include-then-substitute, missing-var and cycle
  both raise with the path), retry (plain-math schedule), jit (frozen
  rule repr, control tool), hooks (first-match wins, wildcard,
  empty-allows), chain (genesis 64 zeros, empty head), snapshot
  (one open run, ZERO_STATE equality), tools (static sorted registry) —
  53 examples / 17 modules, floor pinned by the drill (9/27 -> 17/53);
  first-run catches fixed at the root: doctest qualifies user-defined
  exceptions with their module path (llm's ScriptExhausted expected in
  full), and one announce that landed a commit late with a correction
  note; `oax doctest --min-modules/--min-examples` makes the bar
  operator-grade (floor violated: ..., exit 1) and the drill grows to
  13 checks (cli_floor_enforced), matrix 40 tasks / 460 checks; README
  badge/inline/quickstart/gallery synced, explainers intro + task-40
  prose 13 checks, golden row 40 (13), example 29 step 8, modules.md
  floor-flag note, CHANGELOG round-two bullet; audit 0, doctor 6/6
