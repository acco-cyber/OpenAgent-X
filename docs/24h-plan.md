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
> attempts `git push origin main` anyway so the backlog lands the moment
> credentials return (never force-push, never rewrite history).

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
7. **Push**: `git push origin main` always attempted; on credential failure,
   record it and move on. Never force-push.
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
- [ ] S09-E3 — task 18 `retry-backoff` + task 19 `circuit-breaker`
- [ ] S10-E3 — task 20 `planner-executor` + task 21 `snapshot-travel`
- [ ] S11-E3 — task 22 `prompt-layers` (include order, cycles, substitution)
- [ ] S12-E3 — task 23 `tools-jit` (JIT tool disclosure)
- [ ] S13-E3 — task 24 `chaos` (combined faults in one run) + task 25 `hash-chain`

### Phase 2 — Power tooling & hardening
- [ ] S14-E3 — `oax diff` (event-level journal diff) + `oax stats` (run analytics)
- [ ] S15-E3 — `oax bench` (journal throughput microbench) + fuzz harness (seeded)
- [ ] S16-E3 — property suite (torn-tail/replay/density under random traces)
- [ ] S17-E3 — pack v2 (signed manifest) + sbom v2 (dependency graph)
- [ ] S18-E3 — report v2 (dashboard HTML) + mermaid trace export
- [ ] S19-E3 — examples gallery (budget guard, cache, hooks, replay diff)

### Phase 3 — Docs & ecosystem
- [ ] S20-E3 — docs: module guides + tutorial 0→hero
- [ ] S21-E3 — docs: ADR pack (10 records) + glossary + FAQ
- [ ] S22-E3 — README overhaul (SOTA presentation, badges, demo traces)
- [ ] S23-E3 — CI: GitHub Actions (verify/compileall/eval/audit) + community files
- [ ] S24-E3 — eval parallelism + perf pass + CHANGELOG + 1.0.0-rc1

### Phase 4 — Release
- [ ] S25-E3 — final regression sweep + release 1.0.0 + retrospective

If slots run out before 250 commits, continue with stretch slots (S26-E3+):
per-drill explainers, `oax replay --from`, `oax grep`, more examples — never
pad with empty commits.
