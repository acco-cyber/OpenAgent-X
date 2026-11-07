# OpenAgent-X module guides

One section per module in `openagentx/`, grouped by the job it does. Every
entry names the real public entry points and the invariants the module is
responsible for. The journal — an append-only JSONL event stream — is the
single source of truth; everything else in the package either writes it,
reads it, or proves things about it.

Purity contract for every module: Python 3.10+ standard library only, no
network modules, no third-party imports (`doctor` enforces it), and no
token-shaped literals anywhere (`audit` enforces that).

## The core loop

### events
Append-only event journal (JSONL). `Event` (seq, ts, type, payload),
`Journal` (append / start_run), `read_events`, `read_events_safe`,
`sequence_dense`, `TornMiddleError`. Invariants: seqs are dense 0..n-1 per
run; an unreadable tail (torn write) is isolated and refused loudly; a tear
in the middle is a hard `TornMiddleError`, never silently skipped. Every
other module speaks in events.

### runner
The event-sourced agent loop: think → act → observe → … → reply.
`AgentRunner(llm, tools, journal_path, max_steps, max_tool_calls, workdir,
run_id, hooks, disclosure, journal_cls).run(task)` returns a `RunResult`
(reply, stop_reason, steps, events, journal_path). Also `replay_script`,
`events_summary`. Invariants: every decision lands in the journal
(`run_start` records the caps, `thought`/`tool_call`/`tool_result`/`reply`
carry the loop, `run_end` names the stop reason); `think` is a real tool and
counts against the tool budget; the budget governor stops *before* the
rejected call with a `budget` event naming it; script exhaustion and budget
exhaustion are different stop reasons; a maxed-out run stops
`max_steps` — never a fabricated reply.

### tools
Tool registry and sandboxed builtin tools. `ToolRegistry`, `Tool`,
`ToolError`, `builtin_tools(workdir)` → `calc`, `echo`, `list_dir`, `now`,
`read_file`, `write_file`, `think`, `vault_read`, `vault_bundle`. Invariants:
paths resolve inside the workdir sandbox, args are checked before execution,
tool failures are data (`ok: false` + error) — never exceptions that kill
the loop. The vault tools hold runtime-assembled fixture values so demos can
show redaction without ever storing a real secret shape.

### llm
LLM adapters — offline-first, deterministic. `ScriptedLLM` (a list of JSON
turns; `.cursor` and `.calls` make consumption observable), `EchoLLM`,
`ScriptExhausted`, `ScriptParseError`, `LLMUnavailable`. Invariants: a
scripted run consumes its turns in order; exhaustion is loud; adapters never
touch the network, so drills are reproducible byte-for-byte.

### redact
Redaction engine — high-confidence secret patterns, structure-preserving.
`redact(text)`, `redact_obj(obj)`. Invariants: high-confidence shapes
(`ghp_…`-style tokens, AWS keys, Slack tokens, sk- prefixed keys) become
`[REDACTED:<kind>]`; the surrounding structure and non-secret bytes are
untouched; redaction happens at the view layer *and* is re-applied by every
view, so a secret that leaks into a journal by accident still cannot reach a
rendered report, dashboard, or mermaid export (defense in depth).

### trace
Trace layer: safe loads, deterministic replay, canonical views. `load_trace`
→ `(events, torn)`, `replay` (event fold → run state), `truncate_torn_tail`,
`text_timeline`, `html_report`, `view`. Invariants: replay is a function of
the events alone — two reads fold to one state, wall-clock `ts` never
changes the fold; torn tails are reported, not hidden.

## Views and analytics

### report
Human views over journals: `render_text` (timeline) and `render_html`
(self-contained HTML). Invariants: views are renderings of the journal —
they never recompute or invent; payloads are escaped; output has zero
external assets.

### stats
Run analytics — a deterministic numeric fingerprint of one journal.
`run_stats`, `render_stats`. Invariants: every counter is taken from
`replay()` itself, so stats and replay can never disagree; per-type and
per-tool tables are derived from the same events; wall-clock span is
reported but never graded; no timings in output, so the same file always
yields the same text.

### jdiff
Event-level journal diff — semantic comparison of two event streams.
`diff_events`, `diff_journals(path_a, path_b, strict=False)`, `render_diff`.
Invariants: the default projection ignores wall-clock `ts`; `strict` mode
compares every stored field; `common` is the longest equal prefix,
`removed`/`added` carry the real diverging tails, `diverged_at` names the
split; a self-diff is always `same` with `diverged_at == -1`; torn tails
isolate per side and never corrupt the dense-prefix compare; the CLI
contract is exit 0 same / 1 different.

### dashboard
Report v2 — a deterministic HTML dashboard over one journal.
`dashboard_data`, `dashboard_json`, `dashboard_sha256`, `render_dashboard`.
Invariants: counters come from `run_stats` (which takes replay's) —
dashboard, stats, and replay are three views of one number set and cannot
disagree; integrity strip reports dense/torn flags and duration as
wall-clock, reported not graded; bars are derived from integer counts only;
self-contained HTML (inline CSS, zero external URLs, no scripts, no
timestamps); same file in → byte-identical HTML/JSON out.

### mermaid
Mermaid trace export — the journal as a deterministic flowchart.
`render_mermaid(events, title)`, `trace_mermaid(path)`. Invariants: one
zero-padded node per event with quote-escaped, newline-stripped, 64-char
truncated labels (exactly two raw quotes per line); one spine edge per
consecutive pair; deterministic call/fail/err/say classing; extension event
types render through the generic path; honest zero state for an empty
journal; torn tails diagram the dense prefix only.

### grep
Journal grep — the journal is searchable truth, not just replayable truth.
`grep_journal(path, pattern, etype, tool, since_seq, limit)`, `render_grep`.
Invariants: all matchers AND together (case-sensitive substring over the
type+payload JSON, exact event type, exact payload tool name, a seq floor,
a result cap in seq order); matches render through the redaction engine, so
raw secrets that live on disk can never leak through the search view —
searching for the raw token itself matches (the disk is the truth) and
still prints only the redacted form; torn tails are isolated, never
searched, only reported; the empty result is honest (`matched: 0` with the
scanned total named); no timestamps — same journal and matchers, same
bytes out; CLI contract is exit 0 matched / 1 no matches or missing journal.

### compact
Journal compaction — a deterministic, lossy *secondary* representation.
`compact_events`, `compact_journal`. Invariants: adjacent tool pairs fold
into `tool_fold`; loop bookkeeping drops; the source journal stays
byte-identical; a torn source is refused, never laundered; the output says
it is derived.

### snapshot
Snapshot travel: derived state at any checkpoint of the event stream.
`snapshot_at(events, seq)`, `travel(events, seq)`, `monotone`. Invariants:
snapshots are pure prefix folds — no state is stored, everything is
recomputed from events; bounds errors are loud; torn tails limit how far
you may travel; `monotone` proves checkpoints only move forward.

### replay
Replay from any point — the journal folds from the middle, honestly.
`replay_from(path, from_seq)`, `render_replay(report)`. Invariants: the
suffix fold starts from zero at `from_seq` and folds every event with
`seq >= from_seq`; bounds are honest (0..max seq, an empty journal
exposes only the zero state at 0, out-of-bounds raises `ValueError`,
never silent clamping); density is required — a gapped journal is an
integrity failure, not a state to fold; additivity is claimed only where
it is true (every monotone counter equals whole minus prefix) and never
where it is false (`runs_open` is clamped, `last_reply`/`final_stop`
describe only their own window); a torn tail is invisible to the fold
and reported; the state is the view, and the view renders through the
redaction engine — a raw secret on disk never leaves it, even inside
`last_reply`; the render names its window and carries no timestamps.

### explain
The matrix explains itself from the CLI — one task's spec and its prose
joined. `explain_task(task_path, explainers_path)`, `render_explain(r)`,
`oax explain <NN-slug|path>` (exit 0 found / 1 missing). Invariants: the
report joins the machine-readable contract (drill, task text, script
turns, sorted expect keys, max_steps) with the `### <stem>` prose
section from `docs/explainers.md`; the render is byte-deterministic
with no wall-clock; a task without prose is reported loudly
(`has_prose: False` plus a line naming the verify gate that forbids it)
— never papered over; a missing spec is a loud `FileNotFoundError`/exit
1, not an empty report.

### doctests
Docstring self-checks — the examples are graded, not decorative.
`load_package_modules()` / `load_file_modules(dir)` feed one grading
path; `run_doctests(loaded)`, `render_doctests(report)`,
`oax doctest [dir]` (exit 0 green / 1 failing). Invariants: every
module is reported — with examples or without, and a module with no
examples is counted, never fabricated green; a failing example is loud
(the doctest log with `Failed example` / `Expected` / `Got` rides in
the result); an import failure folds into a failing result carrying
the real exception; one failure poisons the aggregate `ok`; the render
is byte-deterministic with no wall-clock; probes are graded by the
same code that grades the real tree, so a poisoned docstring fails
exactly like a drill fails.

## Reliability

### retry
Retry with deterministic exponential backoff. `RetryLLM`, `BackoffPolicy`,
`RetryExhausted`. Invariants: the schedule is deterministic (no jitter, no
clock), every attempt is logged honestly, give-up is loud with the original
fault, and retries are invisible to the journal — the journal records what
happened, not how many tries it took.

### breaker
Circuit breaker: fail fast while a dependency is down, probe to recover.
`CircuitBreaker`, `CircuitOpen`. Invariants: trip surfaces the *original*
fault (not the breaker's), open state fast-fails without calling the inner
adapter, cooldown ticks on a deterministic clock, and the probe either
closes the circuit or re-opens it — the state machine is honest about which.

### chaos
Chaos engineering for one run. `ChaosLLM`, `ChaosTools`, `chaos_summary`.
Invariants: faults come from a deterministic plan (combined faults in ONE
run), every injection is ledgered, a faulted tool call never executes (zero
side effects), and recovery composes with `RetryLLM` — scars visible,
re-runs identical.

### fuzz
Seeded fuzz harness — random traces, deterministic verdicts. `run_fuzz`,
`run_fuzz_suite`, `render_fuzz`. Invariants: a seeded schedule attacks the
journal contract (torn-tail garbage every 7th op, middle-tear splice every
11th), unicode round-trips, two reads fold to one state, and reports carry
no timings — the same seed always yields the same verdict.

### property
Property suite — journal invariants after *every* step. `run_property_trace`,
`run_property_suite`, `render_property`. Invariants checked continuously:
density is exactly 0..n-1, injected tears isolate AND restore to the exact
pre-tear bytes, the round-trip matches the written plan, `ts` rewrites fold
to the identical replay state — replay is a function of events, never of
the clock.

### bench
Journal throughput microbench. `run_bench`, `render_bench`. Invariants:
deterministic synthetic workload through a real `Journal`, three timed
phases reported as honest single-run wall-clock that is never graded, and a
zero-event bench reports 0.0 rates instead of dividing by zero.

## Orchestration

### team
Two-role team runner: lead → handoff → specialist on ONE shared journal.
`TeamRunner`, `TeamResult`, `team_events_summary`. Invariants: `handoff` is
control-plane (never journaled as a tool call, budget-free), the handoff
carries delegated context to the specialist, and the shared journal tells
the whole story in one file.

### router
Multi-model fallback routing. `FallbackRouter`, `FailingLLM`,
`ModelUnavailable`, `NoModelAvailable`. Invariants: the router walks its
adapter chain per turn, logs every attempt honestly, and a total outage
stops `model_unavailable` — never a fabricated reply.

### fanout
Parallel fan-out: one task, N branches, one coordination journal.
`FanoutRunner`, `BranchResult`, `FanoutResult`, `fanout_fingerprint`.
Invariants: branches are real agents on their own journals; branch failures
are recorded as data on the parent; the coordinator answers only from the
fanin; structure is deterministic across re-runs.

### planner
Planner-executor: one planning turn, N real executor runs. `PlannerExecutor`,
`StepResult`, `PlanResult`. Invariants: plans are fenced, repaired with
notes, and schema-validated; a plan bug stops with `script_error`; failing
steps are data, not crashes; each step runs on its own `step-XX` journal.

### memory
Memory-lite: deterministic TF-IDF recall over past run journals.
`MemoryLite`, `tokenize`, `harvest_texts`. Invariants: the index is built
from what the *redacted* journals already say, so recall can never surface a
raw secret; queries over unknown terms return honest misses, never
hallucinated hits; the index is read-only at recall time.

### prompt
Prompt layers: ordered includes, loud cycle detection, safe substitution.
`PromptLayers`. Invariants: depth-first include expansion in declared
order; include cycles are reported with the full path; diamond includes
expand per path; missing layers and variables name themselves; values stay
literal so data can never inject an include.

### jit
Just-in-time tool disclosure. `JITDisclosure`, `DisclosureRule`,
`JITAgentRunner`. Invariants: turn-zero visibility is journaled; an
undisclosed call is refused *before* hooks with one `tool_hidden` event and
zero side effects; `tools_expand` lands as an ordinary journaled call;
every visibility change journals `tool_disclose` with the full set and the
additions; re-runs are event-for-event identical.

### structured
Structured output. `parse_json_loose` (repair with honest notes: fences,
trailing commas, Python literals, smart quotes, prose-wrapped JSON),
`validate_schema` (lite subset where `True` is never an integer). Invariants:
repair is reported, never silent; hopeless input raises loudly; validation
rejects type confusions a loose `bool`-is-`int` check would wave through.

### cache
Prompt-hash response cache. `ResponseCache`, `CachedLLM`, `prompt_key`.
Invariants: the key is a SHA-256 over the canonical JSON of the exact
message list, so a hit can only serve the very prompt that produced the
stored turn; hits are fresh deep copies (mutation cannot poison the store);
hit/miss counters are honest; the cache sits at the adapter layer, so a
cached run journals exactly like a computed one.

### hooks
Hook policies — pre-tool-call deny rules. `HookPolicy`, `ALLOW`, `DENY`.
Invariants: rules are ordered, first match wins, everything else is
allowed; every decision (allow and deny) is journaled as a `hook` event; a
denied call never reaches the registry (no `tool_call`, no `tool_result`,
zero side effects); the loop continues and the denied attempt still counts
as a step; `rules_snapshot` returns copies, so callers cannot mutate policy
state.

## Integrity and supply chain

### chain
Hash-chained traces — tamper evidence over the journal. `ChainedJournal`,
`compute_chain`, `verify_journal`, `seal`, `event_digest`, `ChainError`.
Invariants: each line commits `{prev, digest}` so any edit, deletion, or
reorder is localized by `verify_journal`; chained fields are invisible to
old readers (plain journals still verify, reported as `chained: false`);
torn tails isolate exactly where sealing stopped; `seal` refuses what it
cannot verify.

### pack
Deterministic pack manifests. `build_manifest`, `manifest_json`,
`write_manifest`, `verify_manifest`. Invariants: the same tree always
yields the same bytes (sorted entries, SHA-256 per file, tree hash over the
canonical manifest), so a manifest is a verifiable fingerprint of content —
not of the clock that made it.

### pack2
Signed pack manifests v2 — integrity plus authenticity. `sign_manifest`,
`verify_signed`, `verify_signature`, `derive_key_id`. Invariants: HMAC-SHA256
over the canonical sig-stripped manifest bytes; `key_id` names the key
without revealing it; verification is constant-time and reports both layers
(content + signature) so a tampered file fails only the content layer while
the signature stays green; v1 manifests still read.

### sbom
Stdlib SBOM — a bill of materials that proves its own purity. `build_sbom`,
`sbom_json`. Invariants: the BOM enumerates the package's own modules and
their stdlib imports, classified honestly; the SBOM of a pure package
contains zero third-party entries, and that absence is a checkable claim.

### depgraph
Import dependency graph — the package's imports as real structure.
`build_depgraph`, `depgraph_json`, `render_depgraph`. Invariants: every
local import resolves to an in-package edge with a kind; eager edges build
longest-path layers with Tarjan cycle detection; lazy function-body edges
are reported as data without tainting the eager layering; entries, leaves,
orphans and fan sums are derived, sorted, timestamp-free.

## Meta and ecosystem

### evaluation
Golden-task evaluation — honest, offline, deterministic drills. `Check`,
`DrillReport`, the `DRILLS` registry. Invariants: drills execute real
behavior from this run (fresh temp workspaces, real journals, real
exceptions); a harness error folds into a failing check — never a skipped
test; the check count only moves forward. Golden tasks are JSON specs in
`golden_tasks/`, graded by `oax eval`.

### doctor
Environment doctor — the purity and integrity gate. `run_doctor`. Six
checks: `python>=3.10`, `stdlib_purity`, `offline_purity`,
`required_files`, `golden_tasks_valid`, `workspace_writable`. Invariants:
the doctor refuses third-party imports and network modules; it validates
the file manifest and the golden-task contracts structurally; it is itself
pure stdlib and offline.

### audit
Secret scanner — the repo audits itself. `run_audit`. Invariants:
token-shaped literals (`ghp_…`, AWS `AKIA…`, Slack `xoxb-`, `sk-ant-` /
`sk-proj-`) are findings; fixture secrets in tests and demos must be
assembled at runtime by concatenation, which the scanner cannot see; the
audit scans the repo including its own documentation.

### cli
`oax` — the command line: `eval doctor audit examples trace report pack
pack2 sbom graph dashboard mermaid run recall compact diff stats grep
replay bench fuzz property`. Invariants: every subcommand has an honest
exit contract (0 = rendered/same/green/folded, 1 = missing/different/
failed, 2 = bad bounds where a window is involved) and prints
deterministic output — the CLI is a thin, scriptable skin over the modules
above.
