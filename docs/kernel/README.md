# The OpenAgent-X kernel — pillar → module map

The reference kernel (``openagentx/``) is the runnable form of the
blueprint. Every pillar is one small module with one job:

| Pillar | Module | What it guarantees |
|---|---|---|
| X-Trace | `openagentx/events.py`, `openagentx/trace.py`, `openagentx/replay.py` | Every state change is a redacted, append-only `EventEnvelope` in JSONL — replayable, auditable, renderable as a timeline |
| X-Gateway | `openagentx/llm.py` | One LLM protocol; EchoLLM (offline), OpenAICompatLLM (any endpoint), RouterLLM (capability routing) |
| X-Budget | `openagentx/budget.py` | Ceilings checked *before* action; write-before-compaction context windows |
| X-Loop | `openagentx/loop.py` | perceive→decide→act→observe with hooks, JSON action protocol, degeneracy guard |
| X-Guard | `openagentx/policy.py` | Pure tri-state policy seam (allow/ask/deny), P0–P4 tiers, capability-text pruning |
| X-Consent | `openagentx/approval.py` | ASK verdicts become hash-bound, one-time, expiring approvals — persisted state, not chat promises |
| X-Tools | `openagentx/tools.py`, `openagentx/builtins.py` | One registry, one dispatch choke point, JIT disclosure, diffs-not-dumps |
| X-Memory | `openagentx/memory.py` | 3-tier JSONL memory: supersede-with-provenance, rollups, human-editable export |
| X-Prompt | `openagentx/prompts.py`, `prompts/base/` | Layered prompt files, `{{include original}}` wrapping, budget-aware trimming |
| X-Packs | `openagentx/packs.py`, `packs/` | Keyword-triggered knowledge packs with declared permissions |
| X-Team | `openagentx/team.py` | Planner/executor/critic with auto-generated delegation catalog |
| X-Eval | `openagentx/evaluation.py`, `golden_tasks/` | Golden tasks as data; offline deterministic grading; reproducible JSON reports |

## Try it (no API keys needed)

```bash
python examples/hello_agent.py     # full kernel run offline
python examples/policy_demo.py     # watch the policy engine decide
python examples/budget_demo.py     # watch ceilings stop a runaway agent
python examples/pack_demo.py       # packs + memory in action
python examples/approval_demo.py   # human-in-the-loop consent for ASK verdicts
oax replay                          # newest run as a timeline (text + shareable HTML)
oax eval                            # golden-task suite, offline, reproducible JSON report
oax doctor && oax run "summarize this repo"   # CLI (after pip install -e .)
```

## Compose it

```python
from openagentx import AgentKernel, EchoLLM, TraceLog, Budget
from openagentx.tools import ToolRegistry
from openagentx.policy import default_policy
from openagentx.builtins import register_builtins

trace = TraceLog()
registry = ToolRegistry(policy=default_policy(), trace=trace)
register_builtins(registry)

kernel = AgentKernel(EchoLLM(), trace, tools=registry, budget=Budget(max_iterations=8))
result = kernel.run("Inspect this workspace and report what you find")
print(result.reply, result.trace_file)
```

Swap `EchoLLM` for `OpenAICompatLLM()` (env-var credentials) or a
`RouterLLM` with profiles — nothing else changes.
