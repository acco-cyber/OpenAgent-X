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

