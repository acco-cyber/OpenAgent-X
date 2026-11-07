# Per-drill explainers — what every golden task grades, and why

The golden matrix (38 tasks, 435 checks) is the repo's contract with
itself: every claim the README, the docs and the CHANGELOG make is
enforced by one of these drills. Each task is an offline, deterministic
JSON spec executed against the real runner and real tools in a fresh temp
workspace, graded by a drill of named checks; exceptions fold into a
failing `harness_error` check — never a skipped one. Run the whole matrix
with `python3 -m openagentx eval` (all green or exit 1).

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

