# OpenAgent-X tutorial — zero to hero

Everything here runs offline with the standard library alone: no API keys,
no network, no third-party packages. Every snippet is executed as part of
the slot that introduced it — if a snippet drifts from reality, the docs
gate in `scripts/verify.mjs` (and your own run of it) will tell you.

Start at step 0; by step 10 you will have written and graded your own
golden drill — the same bar the repository holds itself to.

## Step 0 — the purity gate

Clone, then let the doctor prove the environment before you trust anything:

```sh
python3 -m openagentx doctor   # six checks, 6/6 or exit 1
python3 -m openagentx audit .  # secret scanner over the whole repo
```

The doctor's six checks: `python>=3.10`, `stdlib_purity`, `offline_purity`,
`required_files`, `golden_tasks_valid`, `workspace_writable`. The audit
reports token-shaped literals (`ghp_…`, AWS `AKIA…`, Slack `xoxb-`,
`sk-ant-`/`sk-proj-`); the repo must always be at 0 findings. Fixture
secrets in this codebase are assembled at runtime by concatenation
(`'ghp_' + 'A1b2C3d4E5'*3 + 'F9ab12'`-style) so the scanner can see them
for what they are — never paste a real-looking token into any file.

## Step 1 — your first agent run

An agent is an LLM adapter, a tool registry, and a journal. The scripted
adapter makes runs deterministic and offline (full version:
`examples/01_hello_loop.py`):

```python
import os, sys, tempfile
sys.path.insert(0, ".")  # from the repo root

from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace

wd = tempfile.mkdtemp(prefix="tut1-")
script = [
    '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
    '{"reply": "the answer is 42"}',
]
jp = os.path.join(wd, "journal.jsonl")
result = AgentRunner(ScriptedLLM(script), builtin_tools(wd), jp,
                     max_steps=6, workdir=wd, run_id="tut-1").run("compute 6*7")
print(result.stop_reason, result.reply, result.steps)   # reply the answer is 42 2
events, torn = load_trace(jp)
print([e.type for e in events])
```

The loop is think → act → observe → … → reply, and every decision lands in
the journal: `run_start` (with the caps), `thought`, `tool_call`,
`tool_result`, `reply`, `run_end` (with the stop reason).

## Step 2 — the journal is the only truth

The journal is an append-only JSONL event stream with dense seqs 0..n-1.
Reopen it, replay it, render it — the file, not your memory, is the truth:

```sh
python3 -m openagentx trace tut-journal.jsonl    # text timeline
python3 -m openagentx report tut-journal.jsonl   # self-contained HTML
python3 -m openagentx stats tut-journal.jsonl    # numeric fingerprint
python3 -m openagentx dashboard tut-journal.jsonl  # report v2 HTML
python3 -m openagentx mermaid tut-journal.jsonl    # flowchart export
```

```python
from openagentx.trace import load_trace, replay
events, torn = load_trace("tut-journal.jsonl")
state = replay(events)          # a pure fold of the events
print(torn, state["final_stop"], state["last_reply"])
print(state["tool_calls"], state["replies"], state["steps"])
# False reply the answer is 42 — and the counters replay saw, too
```

Replay is a function of the events alone — read the same file twice, you
get one state; shift every `ts`, you get the same state. A torn tail (a
half-written last line) is isolated and reported, never hidden, and a tear
in the middle raises loudly.

## Step 3 — stop reasons: reply, max_steps, budget, stop

A run ends in exactly one of four honest ways:

- `reply` — the agent answered;
- `max_steps` — the loop hit its step cap (never a fabricated reply);
- `budget` — the tool-call governor stopped the loop *before* the rejected
  call (`examples/18_budget_guard.py` walks the whole story);
- `stop` — the agent called the reserved `stop` tool with an explicit,
  reasoned stop (control-plane: never journaled as a tool call).

```python
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.llm import ScriptedLLM
import os, tempfile

wd = tempfile.mkdtemp(prefix="tut3-")
runaway = [
    '{"action": {"tool": "calc", "args": {"expr": "1+1"}}, "thought": "a"}',
    '{"action": {"tool": "calc", "args": {"expr": "2+2"}}, "thought": "b"}',
    '{"reply": "unreachable"}',
]
r = AgentRunner(ScriptedLLM(runaway), builtin_tools(wd),
                os.path.join(wd, "j.jsonl"), max_steps=8, max_tool_calls=1,
                workdir=wd, run_id="tut-3").run("go")
print(r.stop_reason)   # budget — and the budget event names the refused tool
```

The cap is recorded at `run_start`, executed calls all precede the budget
line, no reply is fabricated, and the scripted tail stays unconsumed.
`think` is a real tool: it spends the budget like anything else.

## Step 4 — secrets: redaction by default

Redaction is a view-layer guarantee with defense in depth
(`examples/02_redaction_demo.py`): the redaction engine rewrites
high-confidence secret shapes to `[REDACTED:<kind>]`, and every view
re-applies redaction to whatever it renders — so even a secret that leaked
into a journal by accident cannot reach a report, dashboard, or mermaid
export. See it end to end:

```python
import os, sys, tempfile
sys.path.insert(0, ".")
from openagentx.redact import redact

tok = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"   # runtime-assembled fixture
out, hits = redact(f"deploy with {tok} now")
print(hits, out)
# 1 deploy with [REDACTED:github_token] now — the count is honest, too
```

```sh
python3 -m openagentx audit .   # the repo auditing itself: 0 findings
```

## Step 5 — cache and policy

Two control-plane features that never touch the loop's honesty
(`examples/19_cache_hits.py`, `examples/20_hooks_deny.py`):

```python
import os, sys, tempfile
sys.path.insert(0, ".")
from openagentx.cache import CachedLLM, ResponseCache
from openagentx.hooks import HookPolicy
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools

wd = tempfile.mkdtemp(prefix="tut5-")
cache = ResponseCache()
inner = ScriptedLLM(['{"reply": "same answer"}'])
shared = CachedLLM(inner, cache)
runner = lambda jp, task: AgentRunner(
    shared, builtin_tools(wd), jp, max_steps=4, workdir=wd,
    run_id="tut-5").run(task)
r1 = runner(os.path.join(wd, "a.jsonl"), "same exact task")
calls_after_first = inner.calls
r2 = runner(os.path.join(wd, "b.jsonl"), "same exact task")
print(inner.calls - calls_after_first)   # 0 — served from the cache
print(cache.stats())                     # honest hits/misses/size

denier = AgentRunner(
    ScriptedLLM(['{"action": {"tool": "calc", "args": {"expr": "1+1"}}, "thought": "t"}',
                 '{"reply": "adapted"}']),
    builtin_tools(wd), os.path.join(wd, "c.jsonl"), max_steps=4, workdir=wd,
    run_id="tut-5b", hooks=HookPolicy([{"tool": "calc", "reason": "disabled"}]))
r3 = denier.run("try calc")
print(r3.stop_reason)   # reply — the deny was journaled, calc never ran
```

Cache keys are SHA-256 over the canonical JSON of the exact prompt: one
changed word is a miss. Hook decisions (allow *and* deny) are journaled as
`hook` events; a denied call never reaches the registry.

## Step 6 — resilience

Transient faults, dead dependencies, and chaos — all deterministic, all
offline (`examples/08_retry_breaker.py`, `examples/12_chaos_chain.py`):

```python
import os, sys, tempfile
sys.path.insert(0, ".")
from openagentx.llm import LLMUnavailable, ScriptedLLM
from openagentx.retry import BackoffPolicy, RetryLLM

class FlakyLLM:
    """Fault double: raises the retryable fault, then serves."""

    def __init__(self, script, fail_first):
        self.inner, self.fail_first, self.calls = ScriptedLLM(script), fail_first, 0

    def complete(self, messages):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise LLMUnavailable("transient")
        return self.inner.complete(messages)

flaky = FlakyLLM(['{"reply": "ok"}'], fail_first=2)
steady = RetryLLM(flaky, BackoffPolicy(max_attempts=4, base_delay=0.001))
print(steady.complete([])["reply"])   # ok — after a deterministic backoff
print(BackoffPolicy(4, 0.001, 2.0).delays())
```

`CircuitBreaker(inner, threshold, cooldown_calls)` fails fast while a
dependency is down and probes to recover, surfacing the original fault.
`ChaosLLM` / `ChaosTools` inject a deterministic plan of combined faults
into one run, ledger every injection, and guarantee a faulted call never
executes.

## Step 7 — orchestration

The framework's team patterns, each honest on its own journal
(`examples/03_team_handoff.py`, and the drills in `golden_tasks/`):

```python
import os, sys, tempfile
sys.path.insert(0, ".")
from openagentx.llm import ScriptedLLM
from openagentx.team import TeamRunner
from openagentx.tools import builtin_tools

wd = tempfile.mkdtemp(prefix="tut7-")
lead = ScriptedLLM([
    '{"action": {"tool": "handoff", "args": {"to": "specialist", "reason": "math delegated"}}, "thought": "reserved control-plane handoff"}',
], name="lead")
spec = ScriptedLLM([
    '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "the delegated math"}',
    '{"reply": "42, verified"}',
], name="specialist")
r = TeamRunner(lead, spec, builtin_tools(wd), os.path.join(wd, "j.jsonl"),
               max_steps_per_role=4, workdir=wd, run_id="tut-7").run("delegate this")
print(r.reply, r.handoffs)   # 42, verified 1 — on ONE shared journal
```

Also in the box: `FallbackRouter` (per-turn model fallback, honest attempt
logs), `FanoutRunner` (one task, N branch agents, failures as data),
`PlannerExecutor` (one planning turn, fenced + repaired plans, real step
journals), `MemoryLite` (TF-IDF recall over past *redacted* journals —
`mem.index_journal(path)` then `mem.recall(query, k=3)`), `PromptLayers`
(ordered includes with loud cycle detection and literal-only substitution),
`JITDisclosure` + `JITAgentRunner` (tool visibility as journaled policy),
`parse_json_loose` + `validate_schema` (repair with notes, honest type
checks).

## Step 8 — prove it

The verification stack, all offline and deterministic:

```sh
python3 -m openagentx diff a.jsonl b.jsonl      # semantic diff, exit 0 same / 1 different
python3 -m openagentx stats a.jsonl             # the numeric fingerprint
python3 -m openagentx property --seed 7         # journal invariants after every step
python3 -m openagentx fuzz --seed 7             # seeded attacks on the journal contract
python3 -m openagentx bench                     # throughput, wall-clock, never graded
```

```python
import os, sys, tempfile
sys.path.insert(0, ".")
from openagentx.chain import ChainedJournal, verify_journal
from openagentx.trace import load_trace

wd = tempfile.mkdtemp(prefix="tut8-")
jp = os.path.join(wd, "chained.jsonl")
j = ChainedJournal(jp)
j.start_run("tut-8")
j.append("note", {"text": "tamper-evident"})
events, torn = load_trace(jp)
print(verify_journal(jp)["ok"], torn)   # True False
```

`ChainedJournal` commits `{prev, digest}` per line — `verify_journal`
localizes any edit, deletion, or reorder. `snapshot_at` / `travel` recompute
state at any checkpoint as a pure prefix fold. `oax dashboard` / `oax
mermaid` export the run; both re-redact whatever they render.

## Step 9 — ship it

Prove what you ship (`examples/04_pack_sbom.py`, `examples/16_pack_graph.py`):

```sh
python3 -m openagentx pack openagentx --out pack.json      # deterministic manifest
python3 -m openagentx pack2 openagentx --key secret --out pack2.json  # + HMAC signature
python3 -m openagentx sbom                                  # stdlib bill of materials
python3 -m openagentx graph                                 # import dependency graph
```

The same tree always yields the same manifest bytes; `pack2` signs the
canonical manifest and reports content and signature layers separately, so
a tampered file fails only the content layer; the SBOM's zero
third-party entries is a checkable purity claim; the depgraph builds eager
layers and names cycles instead of hiding them.

## Step 10 — hero: grade something

The eval matrix is the repository's spine: JSON specs in `golden_tasks/`,
graded by `oax eval` against real runs in fresh temp workspaces. A drill
never trusts its harness: exceptions fold into failing checks, and the
check count only moves forward.

```sh
python3 -m openagentx eval          # 36 tasks, all green or exit 1
python3 -m openagentx examples      # every offline demo, all OK
```

Write your own drill: add a JSON task (id, drill, script, expect — copy
the shape from any existing task), register nothing if the drill name
already exists, and run `oax eval`. Before you commit, the repository's
own bar is the seven-gate verification: `node scripts/verify.mjs`,
`python3 -m compileall -q openagentx examples`, `oax doctor` (6/6),
`oax audit .` (0 findings), `oax eval` (all green, count never regresses),
`oax examples` (all OK), and a staged diff with zero token-shaped
literals. That is the whole discipline: the journal is the truth, the
views never disagree with it, and every green check came from real
behavior in this run.
