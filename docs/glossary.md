# Glossary

Terms as this repository uses them. Module references in parentheses point
at the implementation.

**ADR** — Architecture Decision Record: a dated, numbered document stating
a load-bearing decision, the context that forced it, and its honest
consequences (`docs/adr/`).

**Budget governor** — the runner's tool-call cap: a run with
`max_tool_calls` stops *before* the rejected call, journaling a `budget`
event naming the tool, with `used`/`cap`; the capped attempt still counts
as a step (runner).

**Chained journal** — an opt-in journal wrapper that commits each line to
its predecessor via per-line `{prev, digest}` fields; `verify_journal`
localizes edits, deletions, or reorders; plain journals verify with
`chained: false` (chain).

**Check** — one graded fact in a drill: `Check(name, ok, note)`. The note
is data about what actually happened, not a label (evaluation).

**Control plane** — reserved actions that are never journaled as tool
calls and never spend the budget: the `stop` tool and the team `handoff`
(runner, team).

**Dense sequence** — the journal invariant that event seqs are exactly
0..n-1 per run with no gaps and no duplicates; checked continuously by the
property suite (events).

**Defense in depth (redaction)** — the guarantee that every rendered view
re-applies redaction to whatever it reads, so a secret that reached a
journal by accident still cannot reach a report, dashboard, or mermaid
export (redact, dashboard, mermaid).

**Drill** — one golden task executed for grading: real runner, real
journal, fresh temp workspace, checks derived from observed behavior
(evaluation).

**Event** — one journaled fact: `{seq, ts, type, payload}`. Types include
`run_start`, `step_start`, `thought`, `tool_call`, `tool_result`, `reply`,
`run_end`, plus control-plane and extension types (`hook`, `budget`,
`handoff`, `tool_hidden`, `tool_disclose`, `branch_*`, `step_*`, …)
(events).

**Fingerprint** — a deterministic hash or counter set over a journal or
render: `dashboard_sha256` (HTML bytes), `run_stats` (numeric),
`fanout_fingerprint` (structure). Same input, same fingerprint, always.

**Fixture secret** — a test/demo secret assembled at runtime by
concatenation (`'ghp_' + 'A1b2C3d4E5'*3 + 'F9ab12'`-style) so the audit
never sees a token-shaped literal in the source tree.

**Golden task** — a JSON spec in `golden_tasks/`: id, drill name, script(s),
expect block. The grading matrix; graded by `oax eval`.

**Harness error** — a drill-setup failure (missing file, bad fixture,
crashed builder). It folds into a failing `harness_error` check — it can
never look green or silently skip.

**Hook** — a pre-tool-call policy decision (allow or deny), journaled as a
`hook` event with the reason; first matching rule wins; a denied call
never reaches the registry (hooks).

**JIT disclosure** — just-in-time tool visibility: turn-zero visible set is
journaled; undisclosed calls are refused before hooks with a `tool_hidden`
event; every visibility change journals `tool_disclose` (jit).

**Journal** — the append-only JSONL file of one run's events; the single
source of truth for everything else (events).

**Lazy edge** — an import that happens inside a function body, reported as
data by the depgraph without joining the eager layering (depgraph).

**Manifest** — a deterministic, sorted, hashed inventory of a tree; the
same tree always yields the same manifest bytes (pack). Signed by `pack2`
(HMAC-SHA256 over the canonical sig-stripped bytes).

**Purity gate** — `oax doctor`: six checks (python>=3.10, stdlib purity,
offline purity, required files, golden tasks valid, workspace writable);
6/6 or exit 1 (doctor).

**Replay** — the pure fold of a journal's events into run state (counters,
replies, stop). A function of the events alone: two reads fold to one
state; shifting every `ts` changes nothing (trace).

**SBOM** — the stdlib bill of materials enumerating the package's modules
and their imports; zero third-party entries is the checkable purity claim
(sbom).

**Semantic diff** — a journal diff that ignores wall-clock `ts` by
default; `strict` mode compares every stored byte (jdiff).

**Spine** — the mermaid export's chain of edges linking each event node to
the next; n events yield exactly n-1 spine edges (mermaid).

**Stop reason** — how a run ended, carried by `run_end`: exactly one of
`reply`, `max_steps`, `budget`, `stop` (runner).

**Torn tail** — a trailing, half-written journal line from a killed
process: isolated by the safe reader, reported (never hidden), and
truncatable; a torn line in the middle raises `TornMiddleError` (events).

**View** — any rendering derived from the journal: text/HTML report,
stats, dashboard, mermaid, diff. Views never write; views never invent.

**Zero state** — an honest empty rendering (0 events, no phantom edges,
0.0 rates) rather than a blank or an error (dashboard, mermaid, bench).
