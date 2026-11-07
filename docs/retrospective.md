# Retrospective — the 24-hour SOTA sprint

Written at the release of 1.0.0 (2026-11-07). This document records what
the sprint built, what it lost, what the deliberate costs bought, and what
surprised us. Every number below is the real, machine-checked number — the
same ones `oax eval`, `oax doctor`, `oax audit .` and `scripts/verify.mjs`
re-derive on every commit and in CI.

## The sprint in numbers

| What | Value | Where it is proven |
|---|---|---|
| Parts committed | 25 (`— part 1` … `— part 25`), 5–6 atomic commits each | git log |
| Golden matrix | 36 tasks, 411 checks, all green | `oax eval` |
| Drills behind the tasks | 35 distinct drills; harness errors fold into a failing `harness_error` check | `openagentx/evaluation.py` |
| Runnable examples | 23, each exiting non-zero on its first broken promise | `oax examples` |
| Package modules | 39, every one guided in `docs/modules.md` | `scripts/verify.mjs` gate 4 |
| Required files | 130, every one enforced to exist | `scripts/verify.mjs` gate 1 |
| Secret findings | 0, re-scanned on every drill run | `oax audit .` |
| Doctor checks | 6/6 | `oax doctor` |
| ADRs | 10, each with Status / Context / Decision / Consequences | `scripts/verify.mjs` gate 5 |
| CI | the seven local gates, zero install steps, Python 3.10 + 3.12 | `.github/workflows/ci.yml` |

## Three epochs — what was lost and why

The plan file records the history; the lesson is worth repeating.

- **Epoch 1** (parts 1–53) died with a sandbox reset mid-sprint. Nothing
  survived: the work lived only on a disposable machine.
- **Epoch 2** (parts 1–17, foundation plus a golden matrix at 11 tasks /
  98 checks) was rebuilt and lost the same way — it lived outside the
  durable volume and had never been pushed (origin credentials were absent).
- **Epoch 3** rebuilds at the durable path with the symlink `/home/z/OpenAgent-X`
  → durable location, and pushes every slot commit-by-commit through the
  GitHub REST API (blob → tree → commit → ref per commit, fast-forward only,
  never force-push). Two epochs of loss bought one rule: **the work only
  exists if it is both durable and pushed.**

## What was built

- **The core loop** (part 1): dense append-only JSONL journal with torn-tail
  isolation, replay as a pure fold of events, redaction at the journal
  boundary re-applied by every view, sandboxed builtin tools, the event-sourced
  runner, and the four honest stop reasons.
- **The golden matrix** (parts 1–19): 36 offline deterministic tasks over
  35 drills — loop, redaction, trace, team handoff, router, budget, stop,
  nested redaction, self-audit, packs, SBOM, memory, compaction, cache,
  hooks, fanout, structured output, retry, breaker, planner, snapshot,
  prompt layers, JIT disclosure, chaos, hash chains, diff, stats, bench,
  fuzz, properties, signed packs, depgraph, dashboard, mermaid, the budget
  gallery, and the release sweep.
- **Power tooling** (parts 14–18): `oax diff` / `oax stats` / `oax bench` /
  `oax fuzz` / `oax property` / `oax pack2` / `oax graph` / `oax dashboard` /
  `oax mermaid` — every command with an honest exit-code contract.
- **Docs that cannot drift** (parts 20–22): module guides for all 39
  modules, a zero-to-hero tutorial whose snippets were executed before
  commit, ten ADRs, a glossary of thirty terms, a fifteen-question FAQ,
  and a README whose every claim resolves to something real — guarded by
  verify.mjs gates that fail the build, not just the mood.
- **CI and community** (part 23): the same seven gates on a 3.10+3.12
  matrix with zero install steps (pure stdlib means checkout + interpreters
  is the whole environment), CONTRIBUTING / CODE_OF_CONDUCT / SECURITY /
  bug templates that route people to the mechanical proofs.
- **Release engineering** (parts 24–25): parallel eval with verdict identity
  proven, a profiled perf pass, the release sweep drill, and this document.

## What the deliberate costs bought

The ADRs admit the costs; the retrospective counts what they purchased.

- **Pure stdlib, offline by construction.** Nothing to install, nothing to
  break, nothing to trust transitively: CI runs the whole matrix with only
  a checkout and two interpreters, and the FAQ's most-asked question ("how
  do you test something with zero dependencies?") answers itself — there
  is nothing to install, so there is nothing to go wrong.
- **`ScriptedLLM` instead of a live model.** The eval matrix is
  deterministic: same tasks, same verdicts, byte-stable reports, and drill
  wall-clock around 1.3 s for all 36 tasks. What is *not* claimed honestly:
  nothing here measures model quality. The matrix grades the harness —
  routing, recovery, redaction, orchestration, integrity — not the LLM.
- **Honest grading.** A drill that crashes folds into a failing
  `harness_error` check rather than a silent pass; a green check means the
  behavior was observed in *this* run. This is why the eval count can only
  grow: regressions are impossible to hide, additions are cheap to prove.
- **Timings reported, never graded.** Parallel eval (part 24) recorded the
  honest finding that GIL-bound drills make 4 workers *slower* than serial
  (1.77 s vs 1.37 s pre-optimization) — and shipped anyway, because the
  verdicts were proven identical and the wall-clock is an observation, not
  a grade. The same slot's perf pass profiled the matrix and removed the
  real hot spot (one parse per module instead of two), 1.349 s → 1.247 s
  serial. Measure, report, decide on evidence.

## What surprised us

- **The README-sync gate changed how we write.** Once the README could fail
  the build for naming a subcommand that does not exist or an eval-scale
  number that disagrees with the matrix, docs stopped being a chore and
  became a contract. The same happened to the tutorial (may only name real
  subcommands and existing examples) and the CI workflow (guarded by the
  repo it guards).
- **Negative probes earned their keep.** Every new gate was tested with a
  deliberate lie before it was trusted — a fake subcommand, a typo'd drill
  name, a stale count. The gates that failed loudly on the lie were kept;
  that habit caught real drift more than once during the sprint.
- **The journal made every later feature cheaper.** Because state is a
  pure fold of events, views (diff, stats, dashboard, mermaid, snapshot,
  replay travel) were all projections, not new stores — and the release
  sweep could re-demand every core invariant over one real run in a
  single drill of twelve checks.

## The rules that held

1. Every commit contains real changes; slots are split into 5–6 atomic
   commits; the plan file is the single source of truth for what to build.
2. The eval count only moves forward; doctor stays 6/6; audit stays 0.
3. Fixture secrets are assembled at runtime by concatenation, so a raw
   token never appears in any file — the audit gate proves it every run.
4. Push every slot, one commit at a time, oldest first, fast-forward only.
   Never force-push, never rewrite history. When push fails, record it
   honestly and land the backlog the moment credentials appear.
5. A green check that was not truly observed is a bug of the same severity
   as any code bug. The honest thing to do with a broken gate is fix the
   root cause — never weaken the check.
