# Per-drill explainers — what every golden task grades, and why

The golden matrix (45 tasks, 523 checks) is the repo's contract with
itself: every claim the README, the docs and the CHANGELOG make is
enforced by one of these drills. Each task is an offline, deterministic
JSON spec executed against the real runner and real tools in a fresh temp
workspace, graded by a drill of named checks; exceptions fold into a
failing `harness_error` check — never a skipped one. Run the whole matrix
with `python3 -m openagentx eval` (all green or exit 1), and read any
task's spec + prose from the CLI with `oax explain <NN-slug>`.

This page is the prose map of that matrix. For every task: **the run** —
what actually happens when the drill executes; **the checks grade** — the
invariants that must hold; **loud failure** — what a broken invariant
looks like. Nothing here is aspirational: an invariant that stopped
holding would turn the eval red on the next run.

Tasks are grouped the way `docs/modules.md` groups the modules — by the
job the code does. The specs live in
[`golden_tasks/`](../golden_tasks/README.md) (full JSON per task); the
grading code lives in `openagentx/evaluation.py`.

## The core loop & stopping

### 01-loop-stop — deterministic stop on reply
**The run:** a scripted agent works through tool turns over sandboxed
tools and replies on its final turn; the journal is then re-read from
disk and folded again by an independent reader. **The checks grade (9):**
the loop stops because of the reply (not `max_steps`), seq numbers are
dense `0..n-1`, a reopened journal folds to the identical state, and the
trace view agrees with the fold. **Loud failure:** a reply that fails to
stop the loop, a gap in the sequence, or a reopen that changes the fold —
any of these turns the task red on the next eval.

### 04-loop-budget — the budget governor stops before the rejected call
**The run:** a script makes more tool calls than `max_tool_calls` allows;
the governor must refuse the over-budget call inside the loop. **The
checks grade (10):** a budget event names the rejected tool with
used/cap, the cap is recorded at `run_start`, executed calls are exactly
the pre-budget prefix, the capped attempt still counts as a step, and no
reply is fabricated after the stop. **Loud failure:** a call that
executed past its cap, a budget event missing the tool name, or a
fabricated reply — each is a distinct named check.

### 05-stop-tool — the reserved `stop` tool ends a run with its reason
**The run:** the agent calls the reserved `stop` tool instead of replying.
**The checks grade (10):** `run_end` carries the stop reason, `stop` never
appears as an ordinary tool_call against the registry, prior work in the
journal is preserved untouched, and the journal stays dense through the
reserved path. **Loud failure:** a stop that lost its reason, or one that
corrupted the surrounding event stream.

## Redaction & privacy

### 02-boundary-redaction — secrets die at the journal boundary
**The run:** a tool returns a fixture secret assembled at runtime by
concatenation; the journal, the views and the reply stream are then
inspected separately. **The checks grade (8):** the raw secret exists
only in the tool layer's memory and on the tool's own output path — never
in the journal, never in a view, never in a reply — while
`[REDACTED:github_token]` marks exactly where it was. **Loud failure:**
the raw token shape appearing anywhere outside the redaction boundary
turns the task red immediately.

### 06-redact-nested — deep redaction keeps structure intact
**The run:** a tool returns a nested bundle whose leaves are marked
secret-bearing. **The checks grade (10):** secrets are redacted at the
leaves, the surrounding structure and plain fields survive untouched, and
every view re-redacts on render so no projection can resurrect the raw
value. **Loud failure:** a redaction that flattened the structure, or a
view that printed a leaf the boundary had already caught.

### 07-audit-self — the scanner finds what it is shown, and the repo is clean
**The run:** the audit scanner runs against a planted workspace (runtime
assembled literals) and then against the repository itself. **The checks
grade (10):** planted literals are found with kind/file/line and a
redacted snippet, and the repo's own self-audit reports 0 findings. **Loud
failure:** a planted literal the scanner missed — or a finding in the
repo itself, which fails the task and the slot protocol at once.

## Integrity & recovery

### 03-trace-torn-resume — torn tails isolate, replays agree, resumes stay dense
**The run:** a normal run's journal gets a partial trailing write (a torn
tail); the drill then reads, folds, renders and resumes it. **The checks
grade (9):** the torn tail is isolated (visible in integrity flags, never
folded as an event), truncation restores the exact pre-tear bytes, the
fold is deterministic across reads, the report/trace views agree with the
fold, and a resumed writer continues with dense seq. **Loud failure:** a
tear that corrupted a real event, a fold that changed between reads, or a
resume that left a gap.

### 21-snapshot-travel — checkpoints are pure prefix folds
**The run:** checkpoints are taken at planned seqs, then more events
arrive and the journal is traveled again. **The checks grade (12):** an
earlier checkpoint never changes because of later events or a torn tail,
travel is deterministic and monotone, out-of-bounds/out-of-order/density
violations raise loudly, an empty journal exposes exactly the zero state,
and a reopened journal travels identically. **Loud failure:** a
checkpoint that drifted after the fact — the exact bug prefix-folding
exists to prevent.

### 25-hash-chain — every line commits to its predecessor
**The run:** a journal is sealed with the opt-in hash chain, then
attacked: payload edits, timestamp edits, line deletion, reordering, a
torn tail. **The checks grade (14):** each chained line commits
`{prev, digest}` over the full event JSON, every attack localizes at the
first mislinked line, the head changes under tampering so a recorded
seal exposes it, torn tails leave an intact but unsealable prefix, plain
journals verify honestly as `chained: false`, and resume continues the
chain. **Loud failure:** any tampering that verifies — the one outcome
this module must never allow.

### 29-fuzz-harness — a seeded attacker with a same-seed-same-verdict report
**The run:** a seeded schedule injects a torn tail every 7th op and a
middle tear every 11th op into a real journal while payloads (including
unicode) round-trip. **The checks grade (12):** the schedule fires exactly
per seed, torn tails isolate and truncate to a dense resume, middle tears
raise and restore byte-identically, two reads fold to one state, reports
carry no timings, and the CLI exits 0 iff there were zero violations.
**Loud failure:** an attack that stuck, or a verdict that changed between
runs of the same seed.

### 30-property-suite — invariants re-demanded after every step of a random trace
**The run:** a seeded lottery picks each step — append, torn-tail
injection, or writer restart — and after *every* step the journal is
re-read from disk and re-demanded to prove its invariants. **The checks
grade (12):** density is exactly `0..n-1` after every step, every injected
tear isolates and is strictly refused, truncation restores the exact
pre-tear bytes, the round-trip matches the written plan, replay is
ts-independent (a shifted wall-clock folds identically and the semantic
diff says same), and reports are deterministic. **Loud failure:** any
step after which the journal on disk stopped being what the protocol
claims it always is.

## Supply chain

### 08-pack-roundtrip — manifests you can recompute by hand
**The run:** `oax pack` builds a manifest over a workspace; the drill
then recomputes every hash independently with hashlib. **The checks
grade (10):** the manifest is deterministic (same bytes on a rebuild),
every recorded hash matches the independent recomputation, and
modified/extra/missing files are each detected with their own named
verdict. **Loud failure:** a manifest that drifted between builds, or an
edit that slipped past the diff.

### 09-sbom-pure — the purity verdict is computed, not claimed
**The run:** the SBOM builder parses the package's imports and classifies
them. **The checks grade (10):** the repo's BOM verdict is `stdlib-only`
because the classification says so (not because the README says so),
every import is accounted for, and a planted foreign import flips the
verdict in a controlled probe. **Loud failure:** a third-party import
that reached the package without flipping the verdict — the exact lie the
SBOM exists to catch.

### 31-pack-signed — signatures over canonical bytes, both layers always reported
**The run:** a manifest is signed with HMAC-SHA256 over its canonical
sig-stripped bytes, then verified under wrong keys, edited entries and
tampered files. **The checks grade (12):** two signings are
byte-identical, `key_id` names the key without leaking it, wrong keys and
edited entries fail the signature layer while tampered files fail the
content layer (both layers always reported), the unsigned form is
refused, the v1 verifier still reads the core, and the CLI's sign/check
exit codes hold. **Loud failure:** any tamper class that came back green.

### 32-depgraph — the package's own import graph, layered and acyclic
**The run:** the real package graph is built from actual imports.
**The checks grade (12):** the eager graph is acyclic with zero
unresolved edges, fan sums equal the eager count, the base layer is real
(events/redact at layer 0), `__main__` is an entry reaching the CLI
surface, the genuine deferral ring (cli/doctor/evaluation/sbom) is
reported as lazy edges without tainting the eager layers, synthetic eager
cycles kill the layering while lazy-only cycles keep it, and rebuilds are
byte-identical with a stable `graph_sha256`. **Loud failure:** a hidden
cycle or an unresolved edge in the package itself.

## Orchestration

### 10-team-handoff — two agents, one dense journal
**The run:** a lead agent writes a brief to disk and calls the reserved
`handoff` tool; a specialist agent then reads the brief and answers —
both on one shared journal. **The checks grade (12):** the brief exists on
disk before the handoff, the reserved `handoff` event records its reason,
the specialist's events follow the lead's on the same dense seq space,
and the specialist's reply reflects what it read. **Loud failure:** a
handoff that lost the brief, a forked journal, or a specialist answer
that could not have come from the brief.

### 11-router-fallback — failover that never fabricates
**The run:** the primary adapter fails on cue; the router promotes the
fallback; in a second probe every adapter is down. **The checks grade
(10):** the primary failure is loud, the fallback serves the turn with
every attempt logged, and a total outage stops with
`model_unavailable` — without a fabricated reply. **Loud failure:** a
silent failover, an unlogged attempt, or a reply invented after the
model layer died.

### 16-parallel-fanout — N real branches, failures recorded as data
**The run:** one coordinator dispatches N branch agents, each running for
real on its own journal. **The checks grade (14):** dispatch order is
kept, branch failures land in the fanin as data (`script_error` + empty
reply, never an exception escaping), every child journal carries its
parent's `run_id` reference, and re-runs are structurally deterministic.
**Loud failure:** a branch whose failure vanished, or a child that could
not prove who launched it.

### 20-planner-executor — plans validated before anything executes
**The run:** one planning turn produces a fenced plan; the plan is
repaired with exact notes, schema-validated, and only then fanned out to
real executor runs on their own journals. **The checks grade (14):**
fenced plans repair with named notes, schema violations stop the run
before execution, plan bugs journal an error (never laundered into empty
plans), failing steps are data with dense child journals referenced by
the parent, and re-runs are structurally deterministic. **Loud failure:**
a malformed plan that executed anyway.

### 24-chaos — combined faults in one run, every injection ledgered
**The run:** a deterministic plan injects LLM outages and tool faults
*together* into a single run behind RetryLLM. **The checks grade (14):**
every injection appears in the ledger, RetryLLM's recovery carries its
scars, faulted tool calls never execute (the ghost write leaves no file),
faulted results journal as ordinary `ok:false` tool_results, the
event-type stream matches a healthy run, and re-runs reproduce identical
ledgers. **Loud failure:** an unledgered fault, a side effect from a
faulted call, or chaos that made the journal shape deviate.

## Memory & context

### 12-memory-recall — TF-IDF recall over past runs, honestly ranked
**The run:** several runs are journaled, then queried through the
TF-IDF memory. **The checks grade (10):** the run that actually contains
the queried terms ranks first, rankings are deterministic, unknown
queries return nothing instead of a guess, memory reads past runs
read-only, and what it surfaces passes the redaction engine. **Loud
failure:** a recall that leaked a redacted payload or hallucinated a
hit.

### 13-compaction — fold the steps, keep the truth
**The run:** a finished run's journal is compacted: tool call/result
pairs fold into `tool_fold` events. **The checks grade (13):** the fold
keeps `{tool, ok, redactions}` per pair, step bookkeeping is dropped,
run-level truth survives (start, reply, end), the original file is
byte-identical after the read, and re-compaction is deterministic.
**Loud failure:** a compaction that changed what actually happened, or
one that touched the original bytes.

### 22-prompt-layers — includes expand in declared order, cycles report the path
**The run:** layered prompts with ordered includes, a diamond include, a
cycle, and a missing variable are each expanded. **The checks grade
(13):** depth-first expansion follows declared order (marker positions
prove it), diamonds expand once per path, cycles and self-includes report
the full path, unknown layers and missing variables name themselves,
over-deep chains are rejected, and substituted values stay literal so
data can never inject an include. **Loud failure:** an include that
executed out of order, or a value that smuggled an include in.

## Reliability wrappers

### 14-cache-replay — the cache never changes what happened
**The run:** one script runs twice through a shared `ResponseCache`.
**The checks grade (10):** exact repeats are served without touching the
inner adapter (observable: inner call count stays flat), keys are
canonical and order-sensitive, mutating the cached payload cannot poison
a later hit, and the cached run's journal is identical to the fresh
run's. **Loud failure:** a cache hit that changed the journal, or a key
that collided on content order.

### 15-hooks-deny — the deny lands before the tool does
**The run:** a hook policy denies specific tool calls; the agent keeps
working around the refusal. **The checks grade (11):** denied tools never
execute (zero side effects), every decision — allows included — is
journaled as a `hook` event, first match wins in the rule list, and the
agent observes the denial and still produces a reply. **Loud failure:** a
denied call that reached the registry, or an unjournaled decision.

### 17-structured-output — repair with named notes, refuse with named reasons
**The run:** messy LLM replies (fences, literals, trailing commas, smart
quotes, prose around JSON) go through `parse_json_loose`; hopeless input
and schema violations follow. **The checks grade (11):** every repair
produces its exact note list, hopeless input raises instead of guessing,
the schema rejects missing keys, wrong types, and `True` posing as an
integer. **Loud failure:** a repair that was silently wrong, or a bool
that slipped through an integer gate.

### 18-retry-backoff — retries on a schedule, scars on the record
**The run:** a fault-injected adapter fails transiently; `RetryLLM`
backs off on a deterministic exponential schedule. **The checks grade
(12):** recovery succeeds on the planned attempt, every attempt is
logged, give-up raises loudly with the last fault attached, plan bugs are
never retried, and a retried run journals exactly like a healthy one
(retries are invisible to the event stream). **Loud failure:** a retry
that leaked into the journal, or a give-up that pretended success.

### 19-circuit-breaker — trip, fast-fail, probe, and mean it
**The run:** consecutive real failures trip the breaker; the open circuit
then rejects calls; after cooldown a probe decides the next state.
**The checks grade (12):** tripping surfaces the original fault (not a
generic error), an open circuit fast-fails without consulting the inner
adapter, cooldown rejections are exact, and the probe closes the circuit
or re-opens it; a runner behind a broken breaker stops
`model_unavailable` without fabricating a reply. **Loud failure:** a
half-open state that hid the original fault or called the inner anyway.

### 23-tools-jit — visibility is journaled, refusals have zero side effects
**The run:** a JIT-disclosure runner starts with a hidden tool set;
keyword rules disclose tools mid-run via `tools_expand`. **The checks
grade (14):** turn-zero visibility is journaled before any step,
undisclosed calls are refused with one `tool_hidden` event and zero side
effects (no tool_call, no registry hit), disclosure lands as an ordinary
journaled call, every visibility change records the full set and the
additions, keyword matching is case-insensitive, capped disclosures
truncate sorted without hiding the control plane, and re-runs are
event-for-event identical. **Loud failure:** a hidden tool that executed,
or a disclosure that happened off the record.

## Views & analytics

### 26-journal-diff — the diff that knows wall-clock is not truth
**The run:** two runs of one script, plus deliberately drifted variants,
go through the event-level diff. **The checks grade (12):** two runs of
the same script are semantically SAME (wall-clock ignored), the self-diff
is the zero diff, strict mode diverges at seq 0 over a single edited
timestamp, an edited reply localizes at its seq with both tails verbatim,
deletions and additions land in their named sections, torn tails isolate
per side, and renders are byte-deterministic. **Loud failure:** a diff
that called a real drift "same", or blamed the clock for it.

### 27-run-stats — the fingerprint is replay's counters, verbatim
**The run:** a real run's journal is folded and fingerprinted. **The
checks grade (12):** the fingerprint takes every counter from `replay()`
itself so stats can never disagree with the fold, type counts match the
raw stream and sum to the total, the planned tool profile (calls, the
one planned failure, think counted as a tool) is visible, the per-tool
table pairs calls with ok/fail, the wall-clock span is reported but never
graded, and an empty journal exposes the zero state. **Loud failure:** a
counter that only a second computation path could produce.

### 28-journal-bench — honest timings, never graded
**The run:** a deterministic synthetic workload runs through a real
Journal in three timed phases. **The checks grade (12):** every planned
event lands dense, the three phases report honest single-run wall-clock
with positive rates, bytes re-statted from disk match the plan, doubling
the workload doubles the journal, a zero-event bench reports 0.0 rates
instead of dividing by zero, and no check ever asserts a timing value.
**Loud failure:** a bench that lied about its own structure — timings
themselves are reported, never asserted.

### 33-dashboard — one HTML file, one source of numbers
**The run:** a run is rendered to the v2 HTML dashboard, including a
probe journal with a hand-written raw token. **The checks grade (12):**
the dashboard's counters are taken from `run_stats` (which takes
replay's) so dashboard/stats/replay never disagree, type counts match the
raw stream, the planned tool profile lands in the per-tool table with
read_file named, renders are byte-identical with a stable sha256, the
HTML is self-contained (doctype, inline style, zero external URLs, zero
scripts), the raw hand-written token is re-redacted by the view, and
empty/torn states render honestly. **Loud failure:** a dashboard number
that no journal fold could produce, or a leak through the timeline.

### 34-mermaid — the trace you can paste into a diagram
**The run:** a real run's journal renders to Mermaid. **The checks grade
(11):** the first line is exactly `flowchart TD`, every event gets one
zero-padded node with a quote-escaped, newline-stripped label, spine
edges chain every consecutive pair, the planned failure carries the fail
class while replies and run ends carry say, extension event types render
through the generic path, re-renders are byte-identical, and torn tails
diagram the dense prefix only. **Loud failure:** a node that escaped its
label or a diagram that imagined an event.

## Search & replay

### 37-grep-journal — searchable truth whose search view cannot leak
**The run:** matchers (substring over the type+payload JSON projection,
exact event type, exact payload tool name covering call+result pairs, a
seq floor, a seq-ordered limit cap) are fired at real journals — including
one with a hand-written raw token. **The checks grade (12):** matchers
AND together, the empty result is honest (matched 0 with the scanned
total named), torn tails are isolated and never searched while the dense
prefix searches identically, the raw token matches on disk (the disk is
the truth) yet prints only `[REDACTED:github_token]` — even when the
pattern *is* the raw token — output is byte-deterministic with no
wall-clock, and the CLI exits 0 matched / 1 none / 1 missing with
redacted stdout. **Loud failure:** a search that printed what the
boundary exists to hide.

### 38-replay-from — the journal folds from the middle, honestly
**The run:** a real run is replayed from seq 0, from the second action's
step_start, and from max seq; bounds, gaps and torn tails are probed.
**The checks grade (12):** from 0 is the whole run, every monotone
counter of a mid-run suffix equals whole minus prefix (11 counters), the
non-additive fields — clamped `runs_open`, window-local
`last_reply`/`final_stop` — describe only their own window, from max seq
folds exactly one event, out-of-bounds raises `ValueError` (never
silently clamped), a gapped journal is an integrity failure that raises
instead of folding, a torn tail is invisible to the fold and reported,
the render names its window and is byte-deterministic, a raw token inside
a reply never leaves the state view, and the CLI exits 0 folded / 1
missing / 2 bad bounds. **Loud failure:** a fold that claimed additivity
where it is false — the honest-refusal contract is the feature.

## The meta-drills

### 35-budget-gallery — the gallery's story graded end-to-end
**The run:** example 18's budget story — cap 3, two writes planned — is
re-run and graded as a golden task, not just watched. **The checks grade
(10):** think/calc/first-write execute as exactly the pre-budget prefix,
the second `write_file` attempt is refused before the registry with the
budget event naming it (used=cap=3, rejected_tool `write_file`), the cap
is recorded at `run_start`, `run_end` carries `stop_reason: budget`, no
reply is fabricated, the capped attempt still counts as a step, the
scripted tail stays unconsumed, and journals reopen dense. **Loud
failure:** any divergence between the example's narrative and what the
run actually did.

### 36-release-sweep — the release regression sweep on one real run
**The run:** one real run is folded, rendered, diffed, chained, audited
and doctor-checked in a single sweep. **The checks grade (12):** stats
and dashboard counters agree with each other and with the raw stream,
report/trace/dashboard/mermaid re-render byte-identically, the planned
tool profile matches, the self-diff is the zero diff, a runtime
hand-written raw token is re-redacted by both views, a chained journal
verifies + seals + verifies, the repo audits to 0 findings, doctor passes
6/6, and `__version__` equals the top CHANGELOG entry. **Loud failure:**
any single invariant slipping — this task exists so a release cannot go
out while one of them is quietly broken.

### 39-explain — the explainer view: the matrix explains itself from the CLI
**The run:** no agent runs here; the drill grades the join between a
task's machine-readable spec and its prose on this page. **The checks
grade (14):** a real task explains (id, drill and prose all present), the
report's fields match the JSON file read independently, expect keys come
back sorted, the render carries both halves (spec line + prose body) and
is byte-deterministic with no wall-clock, prose coverage is
cross-checked in both directions (every golden task has an entry here,
every entry names a real task), a foreign spec without prose is reported
loudly (`has_prose: False` naming the verify gate — never fabricated
prose), a missing spec raises instead of an empty report, and the CLI
agrees (exit 0 found / 1 missing), and the matrix index covers
every task in sorted order (deterministic render, CLI exit 0 covered,
a ghost spec without prose a loud NO-PROSE row — coverage reported,
never fabricated). **Loud failure:** a task added
without its prose, or an explain render that drifted between calls.

### 40-doctest — docstring self-checks: the examples are graded, not decorative
**The run:** no agent runs here either; the drill grades the package's
own docstring examples through the stdlib doctest engine — the same
loaders that grade the real tree also grade the probe files this drill
writes, from the same fresh single-threaded interpreter (the engine
swaps the process-global stdout around every example; a child isolates
it from the parallel eval pool instead of racing it). **The checks grade (13):** the real tree is green (53 examples
across 17 modules, floor pinned so the set cannot quietly shrink), every
package module is reported in sorted order with none skipped, modules
without examples are counted honestly and never faked green, a poisoned
docstring (`add(2, 3)` promised 6, got 5) fails loudly with its log, the
log carries `Failed example` / `Expected` / `Got`, an import bomb folds
into a failing result carrying the real `RuntimeError`, the redaction
example is really graded (fixture assembled at runtime, marker in,
raw token never printed), the render is byte-deterministic with no
wall-clock, one failure poisons the aggregate, and the CLI agrees
(exit 0 green / 1 failing), and the floor flags work from the CLI too (`--min-examples 9999` fails loudly naming the floor). **Loud failure:** a docstring example that
rots — the first run of this very drill caught two examples referencing
a name their module never imported — or a probe that somehow passes.

### 41-attest — the release attestation: one command, one artifact, every gate
**The run:** no agent runs here either; the drill drives
`openagentx/attest.py` in a fresh child interpreter (the doctest gate
runs the doctest engine, whose stdout swapping must not race the eval
pool — the doctest drill's discipline, inherited): the real tree and
four synthetic probe trees are collected, rendered and serialized
through the exact same five-gate path an operator's `oax attest` runs.
**The checks grade (12):** the real tree attests green with the five
gates in fixed order (doctor, audit, doctests, manifest, matrix); the
doctest gate's counts are floor-pinned (17 modules / 53 examples) so
the example set cannot quietly shrink; the matrix gate covers every
task with prose and every expect key; the manifest gate's tree hash
matches an independent build; a synthetic probe tree attests green
(the gates are root-parametric, one grading path for real trees and
probes); an import bomb folds the doctest gate red carrying the real
`RuntimeError` in the gate detail; a runtime-assembled planted secret
turns the verdict red with the file named and the secret never echoed;
a gate that crashes (a required-files path that is a directory) folds
red carrying the real `IsADirectoryError`; renders are
byte-deterministic twice with no wall-clock; the machine artifact is
byte-identical twice, sort_keys-sorted, and carries the 64-hex tree
hash; the CLI exits 0 green / 1 red with the render on stdout.
**Loud failure:** a planted credential on disk — attest names the file
and the finding kind without ever echoing the secret, and the verdict
goes red the moment one gate is red.

### 42-runs — the multi-run index: a directory of journals, one honest table
**The run:** no agent runs here either; the drill builds a fresh
temp directory of four synthetic journals written as canonical
`Event` JSON with fixed timestamps (one clean, one with a torn tail,
one torn in the middle, one carrying a runtime-assembled planted
secret in a payload) plus one noise file, then drives
`openagentx/runs.py` over it — the exact code path an operator's
`oax runs <dir>` executes.
**The checks grade (12):** rows sorted by file name with the render
byte-identical twice; every row's counters equal `run_stats` of that
same journal (one grading path — the index can never disagree with
`oax stats`); the totals row sums exactly what the rows sum (10 events
/ 3 calls / 3 results / 1 fail — the drill's first run caught its own
assertion saying 11 and was corrected against the real sum, never
against a wish) and never claims a duration (spans overlap); a torn
tail is flagged but still indexed with the intact prefix counted; a
middle-torn journal folds into a loud `TornMiddleError` error row with
no directory prefix leaked; the planted payload secret never reaches
the render or the artifact; an empty directory is honest emptiness
(`ok` False, loud render); non-JSONL files are ignored; the artifact is
byte-identical twice under `sort_keys` with no directory path; no
10+-digit wall-clock number anywhere; a missing directory raises with
the path named; the CLI exits 0 indexed / 1 nothing to index.
**Loud failure:** the middle-torn probe, the planted-secret probe and
the missing-directory probe all grade the fold, not the hide — an
index that skipped a damaged journal or echoed a payload would fail
`middle_torn_loud_error_row` / `no_payload_leak` / `empty_dir_loud`.

### 43-doctor — the auditor audits itself: the gates graded at their edges
**The run:** no agent runs here either; the drill drives
`openagentx/doctor.py` over the real tree (6/6 gates) and over fresh
temp workspaces planted step by step with the defects the gates
exist to catch — a third-party import, a network import, a missing
required file, a truncated JSON spec, an unknown drill name — parsed
only, never executed, everything rebuilt per invocation.
**The checks grade (12):** the real tree green (6/6); the verdict
render byte-identical twice with no 10+-digit wall-clock number; a
clean synthetic workspace green too (purity is the absence of
offenders, not the presence of this repo); the planted `numpy` import
caught by `stdlib_purity` with `foreign.py:numpy` named; the planted
`socket` import caught by `offline_purity` with `netty.py:socket`
named; the missing `gone.txt` named by `required_files`; the
truncated spec folded into `golden_tasks_valid` carrying the real
exception without crashing the doctor; the unknown-drill spec named
by the same gate; the gates proven independent — one poisoned tree
turns exactly the four planted gates red, never more; the CLI exits
0 green / 1 red with the verdict and the failing gates in stdout.
**Loud failure:** every probe grades the catch, not the silence — a
doctor that swallowed an import, clamped a missing file or faked a
verdict would fail `foreign_import_caught` / `missing_required_named`
/ `red_gates_counted` / `cli_red_contract`.

### 44-chain-cli — tamper evidence from the CLI: verify and seal
**The run:** no agent runs here either; the drill writes a real
chain-written journal with the module's own line writer over fixed
canonical `Event`s in a fresh temp workspace, then tampers with real
copies — one edited payload byte, one deleted line, one reordered
pair, one truncated tail — and drives `oax chain` over every one,
plus the seal refusals and the missing path.
**The checks grade (12):** the fixture verifies with the stored head
equal to an independent recomputation and the genesis convention
(64 zeros) visible on disk; the CLI's verify render is byte-identical
to the module's and stable twice, exit 0; the edited byte, the deleted
line and the reordered pair are each localized at the first mislinked
index with the CLI naming it; a torn tail is an incomplete file — the
intact prefix still reports ok but the CLI exits 1 with `+torn_tail`;
`--seal` prints exactly the module's seal (the 64-hex head); plain,
empty and torn journals are refused with their reason named and no
traceback; a plain journal verifies honestly as plain; a missing
journal is named, never blessed; module render == CLI render; no
10+-digit wall-clock number anywhere.
**Loud failure:** every tamper probe grades the localization, not the
silence — a CLI that blessed an edited journal, a torn file or an
absent path would fail `tampered_payload_localized` /
`torn_tail_exit_one` / `missing_journal_named`; a seal over
unverifiable bytes would fail `seal_refusals_named`.

### 45-species — redaction species round three: the table learns six more shapes
**The run:** no agent runs here either; the drill exercises the
redaction engine and the audit scanner directly over runtime-assembled
fixtures in a fresh temp workspace — each new species planted in a
real file, one journal carrying a raw secret through `oax grep`'s
view, and the repository itself re-scanned.
**The checks grade (13):** each of the six new species (google_api_key,
gitlab_pat, stripe_secret, npm_token, jwt, private_key_block) caught
with its kind named and the raw value gone; Stripe's test mode caught
like live mode; the RSA, OPENSSH and PGP-BLOCK private key variants
all caught; the near-misses left alone — an AIza tail one char short,
a 19-char GitLab token, a 15-char Stripe body, a 35-char npm token, a
JWT missing its signature, a CERTIFICATE block (high-confidence, not
a spell-checker); the five legacy species still caught after the
table grew; one line carrying three species reports exactly three
redactions; audit over the planted tree finds all six kind-by-kind
with every snippet itself redacted and two scans byte-identical; the
repository still audits to 0 findings; the grep render shows only the
redacted form, byte-identically twice with no wall-clock; and the
table is pinned at eleven species so it cannot silently shrink.
A weakened table would fail `six_new_species_caught`; a
false-positive-prone one would fail `near_misses_invisible` and
`repo_self_audit_clean`.

## Adding a task

New tasks follow the rules in
[`golden_tasks/README.md`](../golden_tasks/README.md): spec JSON with
`id` + `drill` + the shape required by that drill family, fixture secrets
assembled at runtime by concatenation, checks that observe real behavior
from *this* run, and an explainer entry on this page. The explainer gate
in `scripts/verify.mjs` fails the build for any golden task without its
`###` entry here — and for any entry here that does not name a real
task. The matrix only grows, and so does its prose.
