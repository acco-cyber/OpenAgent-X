# 00 — AI Context (read this first)

OpenAgent-X is a **pure-stdlib Python 3.10+ agent framework**. Everything is
event-sourced: the JSONL journal is the only truth; views (text/HTML) are
derived; replay must be deterministic. This repo is the **Epoch 3** rebuild —
it lives on the durable volume (`/home/z/my-project/OpenAgent-X`, symlinked
from `/home/z/OpenAgent-X`) because two earlier epochs were lost to sandbox
recycling. `docs/24h-plan.md` is the operating contract for every slot.

## Architecture map

```
events.py      Event dataclass, append-only Journal (dense seq), strict/safe reads,
               torn-tail isolation (safe read isolates a trailing torn line;
               strict read raises TornMiddleError), sequence_dense()
redact.py      high-confidence secret patterns; redact()/redact_obj() →
               "[REDACTED:<kind>]" markers; used at the journal boundary;
               object walk rewrites leaves only (structure survives)
llm.py         ScriptedLLM: single-line JSON turns {"action":{tool,args},thought}
               or {"reply":...}; ScriptExhausted/ScriptParseError are honest
               failures; LLMUnavailable bases the routing stop reasons
tools.py       ToolRegistry (result envelopes {"ok","result"|"error"}), sandboxed
               fs tools (paths must resolve inside workdir), AST-safe calc,
               vault_value(): runtime-concatenated fixture credentials;
               vault_bundle(): nested fixture bundle (deep-redaction drill)
runner.py      AgentRunner loop: run_start → (step_start → thought? → tool_call/
               tool_result | reply | stop_tool) → run_end; stop reasons:
               reply | stop_tool | budget | max_steps | script_error |
               model_unavailable (LLMUnavailable from routing); redacts payloads
               BEFORE journaling; tools execute on real values; max_tool_calls
               governor journals a `budget` event and stops BEFORE the capped call
team.py        TeamRunner: lead→specialist handoff on ONE shared journal;
               role-tagged events (role_start/handoff); `handoff` is a reserved
               control-plane action (journaled as `handoff`, never tool_call);
               stop reasons add handoff_rejected; specialist history carries
               the HANDOFF observation
router.py      multi-model fallback routing: first healthy adapter serves; every
               attempt recorded in an honest per-run log; FailingLLM injects
               outages; NoModelAvailable → explicit model_unavailable stop
report.py      render_text / render_html (self-contained, escaped, no timestamps
               in views); re-redacts (defense in depth)
trace.py       load_trace (safe), replay (pure deterministic fold),
               truncate_torn_tail (recovery), views
evaluation.py  golden-task harness: JSON specs → drills of named Checks;
               exceptions fold into failing harness_error; DRILLS registry
               (loop, redact, trace, team, router, budget, stop,
               redact_nested, audit, pack, sbom, memory, compact, cache,
               hooks, fanout, structured)
doctor.py      python>=3.10, stdlib purity (AST import scan vs sys.stdlib_module_names),
               offline purity (no net modules), required files, task contracts
audit.py       secret-scan of the whole tree; must be 0 findings on this repo
pack.py        deterministic tree manifests: sha256 per file, sorted
               timestamp-free entries, canonical JSON, verify_manifest()
               itemizes missing/modified/extra honestly
sbom.py        stdlib bill of materials: imports classified stdlib/local/
               foreign per module; stdlib_only is a computed verdict;
               network modules flagged separately; deterministic bom hash
memory.py      MemoryLite: TF-IDF recall over past-run journals — read-only
               derived view, smoothed idf, deterministic ranking, redaction
               preserved (indexes only what the journal already says)
compact.py     journal compaction: tool_call+tool_result pairs fold into
               tool_fold {tool, ok, redactions}; step bookkeeping dropped;
               original untouched; torn sources refused; byte-deterministic
cache.py       ResponseCache + CachedLLM: sha256 canonical prompt keys,
               deepcopy hits, honest hit/miss counters; cached runs journal
               identically to computed ones
hooks.py       HookPolicy: ordered pre-tool-call deny rules, first match
               wins; runner journals every decision as a hook event and a
               denied call never reaches the registry
fanout.py      FanoutRunner: one task → N real branch agents on their own
               journals; parent journals branch_start/branch_end/fanin;
               failures recorded as data; structural determinism (fixed
               run_ids → identical seq/run_id/type/payload stream)
structured.py  parse_json_loose: ordered repair pipeline (smart quotes,
               fences, Python literals, trailing commas, balanced
               extraction) with honest notes, loud ValueError on hopeless
               input; validate_schema: lite JSON-Schema subset, bool is
               never integer/number
cli.py         oax eval|doctor|audit|examples|trace|report|run|pack|sbom|recall|compact
```

## Invariants (never break)

1. **Append-only**: journals are never rewritten; recovery only truncates an
   isolated torn tail (bytes after the last complete line).
2. **Dense sequences**: `seq` is 0..n-1, no gaps, ever.
3. **Redaction boundary**: payloads are redacted *before* journaling; views
   re-redact; tools still execute on real values (truth vs observation).
4. **Honest grading**: a green check means the behavior was observed in this
   run. Drill crashes → failing `harness_error`. No skip, no snapshot, no cache.
5. **Pure stdlib + offline**: no third-party imports, no network modules —
   enforced by `oax doctor`.
6. **Eval count only grows**: golden tasks are never deleted or weakened.
7. **Audit-clean repo**: any fixture secret is assembled at runtime by
   concatenation (e.g. `"ghp_" + "A1b2C3d4E5"*3 + "F9ab12"`) so `oax audit .`
   stays at 0 findings. Never paste literal token-shaped strings.
8. **Durable home**: the repo lives under `/home/z/my-project/` (survives
   recycling). Never move it back to the ephemeral volume.

## ScriptedLLM protocol

- Turn line: `{"action": {"tool": "name", "args": {...}}, "thought": "..."}`
  or `{"reply": "..."}`; one JSON object per line.
- `think` is a real tool and counts in `expect.tool_calls`.
- Script exhaustion raises `ScriptExhausted` → journaled `error` +
  `script_error` stop; it is NOT `max_steps`.

## Verification gate (every slot, before the final commit)

`node scripts/verify.mjs` · `python3 -m compileall -q openagentx examples` ·
`python3 -m openagentx doctor` (6/6) · `python3 -m openagentx audit .` (0) ·
`python3 -m openagentx eval` (all green) · `python3 -m openagentx examples`
(all OK) · staged-diff secret grep (0 matches).
