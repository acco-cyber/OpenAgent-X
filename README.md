<div align="center">

# ⚡ OpenAgent-X

**Any model. Full agency. Minimum tokens.**

The budget-first agentic kernel + universal AI understanding package —
everything an AI *or a human* needs to run capable, safe, auditable agents
with a token bill you control.

[![CI](https://github.com/acco-cyber/OpenAgent-X/actions/workflows/ci.yml/badge.svg)](https://github.com/acco-cyber/OpenAgent-X/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![deps](https://img.shields.io/badge/required%20deps-0-brightgreen.svg)](pyproject.toml)
[![GitHub stars](https://img.shields.io/github/stars/acco-cyber/OpenAgent-X.svg?style=social)](https://github.com/acco-cyber/OpenAgent-X/stargazers)

</div>

---

## Why developers star this repo

Every agent framework promises autonomy; most deliver **runaway loops,
unverified claims, and expensive-model-for-everything**. OpenAgent-X attacks
all three *structurally*, in ~2,000 lines of dependency-free Python:

| Your pain | OpenAgent-X answer |
|---|---|
| 💸 Surprise API bills | **X-Budget** — hard ceilings (tokens / tool calls / iterations / wall clock) checked *before* every action; runaway agents stop at 5/5, not at $50 |
| 🕵️ "What did the agent do?!" | **X-Trace** — every state change is an append-only JSONL event envelope; replay any run with `jq` |
| 🎭 Tool-call lock-in | **X-Loop** — a plain-text JSON action protocol that works with *any* model, no function-calling required |
| 🔓 Prompts that grant power | **X-Guard** — a pure policy engine (allow / ask / deny) owns every decision; denied tools *vanish from the prompt* |
| 🧠 Amnesia & contradictions | **X-Memory** — supersede-with-provenance, evidence-gated promotion, human-editable files |
| 📦 Heavy frameworks | **stdlib-only core** — `pip install -e .` or just copy the `openagentx/` folder |

## 30-second quickstart (zero API keys)

```bash
git clone https://github.com/acco-cyber/OpenAgent-X.git
cd OpenAgent-X
python examples/hello_agent.py      # full agent kernel, offline, deterministic
```

```text
status     : run.done
iterations : 2
tokens     : 455
model      : echo-1

trace: 8 events in .openagentx/traces/….jsonl
    2 × kernel.iteration
    2 × agent.model_selected
    1 × task.completed …
```

Then try the rest — each demonstrates one pillar end-to-end:

```bash
python examples/policy_demo.py   # watch allow/ask/deny verdicts get enforced
python examples/budget_demo.py   # watch ceilings stop a runaway agent
python examples/pack_demo.py     # knowledge packs + memory recall
python examples/approval_demo.py # human-in-the-loop consent for ask-gated tools
python -m openagentx.cli replay  # newest run as a timeline (text + one-file HTML)
python -m openagentx.cli eval    # golden-task suite, graded offline, reproducible report
python -m openagentx.cli doctor  # environment check (never prints secrets)
python -m openagentx.cli run "build a responsive landing page"  # packs auto-activate
```

Go online by exporting credentials (read from env — never hardcoded, never logged):

```bash
export OPENAGENTX_API_KEY="…"      # or any OpenAI-compatible endpoint:
export OPENAGENTX_BASE_URL="https://api.openai.com/v1"   # vLLM, Ollama, OpenRouter…
export OPENAGENTX_MODEL="gpt-4o-mini"
python -m openagentx.cli run "research and summarize the top 3 JS frameworks" --online
```

## The twelve pillars

| Pillar | Module | One-line guarantee |
|---|---|---|
| **X-Trace** | `events.py`, `trace.py`, `replay.py` | Every state change is a redacted, append-only `EventEnvelope` — replayable as a text or one-file HTML timeline |
| **X-Gateway** | `llm.py` | One protocol; offline EchoLLM, any OpenAI-compatible endpoint, capability-aware routing |
| **X-Budget** | `budget.py` | Ceilings before action; write-before-compaction context windows |
| **X-Loop** | `loop.py` | perceive→decide→act→observe with hooks; degeneracy guard kills repetition loops |
| **X-Guard** | `policy.py` | Pure tri-state policy seam (allow/ask/deny), P0–P4 tiers, deny-closed default |
| **X-Consent** | `approval.py` | ASK verdicts become hash-bound, one-time, expiring human approvals — persisted state, never a chat promise |
| **X-Tools** | `tools.py`, `builtins.py` | One registry, one dispatch choke point, JIT tool disclosure, diffs-not-dumps |
| **X-Memory** | `memory.py` | 3-tier file memory: supersede-with-provenance, daily rollups, `MEMORY.md` you can edit |
| **X-Prompt** | `prompts.py`, `prompts/base/` | Layered prompt files; `{{include original}}` wraps defaults — extend, never fork |
| **X-Packs** | `packs.py`, `packs/` | Keyword-triggered knowledge packs with *declared* permissions |
| **X-Team** | `team.py` | Planner → budgeted executors → evidence-gated critic; auto-generated delegation catalog |
| **X-Eval** | `evaluation.py`, `golden_tasks/` | Golden tasks as data — offline, deterministic grading with reproducible JSON reports |

Full map with compose-it snippets: **[`docs/kernel/README.md`](docs/kernel/README.md)**.

## Universal AI understanding package

This repo is *also* a complete operating context for any AI system — the
original mission. Point Claude, GPT, Gemini, Cursor, Copilot, or any agent
framework at it:

1. **[`AGENTS.md`](AGENTS.md)** — the complete self-contained operating context (prime directives, task lifecycle, permission model, event/memory contracts).
2. **[`openagent-x.manifest.json`](openagent-x.manifest.json)** — machine-readable architecture, task states, permission tiers.
3. **[`schemas/`](schemas/)** — 8 JSON Schema contracts (`Task`, `Plan`, `AgentDefinition`, `EventEnvelope`, `MemoryRecord`, `Approval`, …) with TypeScript mirrors in [`contracts/`](contracts/types.ts).
4. **[`docs/blueprint/`](docs/blueprint/README.md)** — the 24-section engineering blueprint.
5. **[`docs/agentic-mode/`](docs/agentic-mode/README.md)** — operating protocols for full agentic potential at minimal cost: planning, verification, cost optimization, safety, prompt pack.

The kernel **implements the contracts**: traces validate against
`event-envelope.schema.json`, memory records against `memory-record.schema.json`,
and permission tiers match the manifest's P0–P4 scale.

## What we synthesized (and how)

Built by studying five reference systems and fusing their best *patterns*
into something new — concept-level inspiration only, zero code copied
(license-aware: MIRA is AGPL-3.0, so pattern inspiration only):

| Reference | Pattern we fused | Where it lives now |
|---|---|---|
| [OpenHands](https://github.com/OpenHands/OpenHands) | Event-sourced traces; condensation as an event | X-Trace envelopes, budget events |
| [Agent Zero](https://github.com/agent0ai/agent-zero) | Prompts-as-files with override layers; auto-generated delegation catalog | X-Prompt layers, X-Team catalog |
| [Interpreter Workstation](https://github.com/openinterpreter/interpreter-workstation) | One tool choke point; diffs-not-dumps; denial parity | X-Tools registry, X-Guard |
| [MIRA](https://github.com/Vexillon-ai/MIRA) | JIT tool disclosure; degeneracy guard; memory supersede + rollups; write-before-compaction | X-Tools `find_tools`, X-Loop, X-Memory, X-Budget |
| [OpenAgent](https://github.com/the-open-agent/openagent) | Tri-state tool policies; guardrail verdict pipeline | X-Guard policy engine |

And the **anti-patterns** we deliberately avoided: monolithic agent loops,
per-vendor client sprawl, policy inside prompts, admin-platform sprawl,
stores you can't `grep`.

## How OpenAgent-X compares

| | OpenAgent-X | Big frameworks | Raw SDK usage |
|---|---|---|---|
| Required dependencies | **0** | dozens | 1+ |
| Read the whole core in an afternoon | **yes (~2k LOC)** | no | n/a |
| Hard run budgets, enforced | **built-in** | rarely | DIY |
| Per-call policy engine + audit trail | **built-in** | partial | DIY |
| Offline demo with zero API keys | **yes** | rarely | rarely |
| Copy the folder into your app | **yes** | no | yes |

OpenAgent-X is a **kernel + spec**, not a platform: compose it into your
product instead of migrating into someone else's.

## Repository map

```
OpenAgent-X/
├── AGENTS.md                    # ★ AI agents start here
├── openagent-x.manifest.json    # machine-readable system manifest
├── openagentx/                  # ★ the reference kernel (stdlib-only)
│   ├── events.py  trace.py      #   X-Trace
│   ├── llm.py                   #   X-Gateway (offline / OpenAI-compat / router)
│   ├── budget.py  loop.py       #   X-Budget + X-Loop
│   ├── policy.py  tools.py  builtins.py   # X-Guard + X-Tools
│   ├── memory.py  prompts.py  packs.py    # X-Memory + X-Prompt + X-Packs
│   ├── team.py  cli.py          #   X-Team + oax CLI
├── prompts/base/                # layered prompt files
├── packs/                       # web-dev · data-science · devops · research · writing
├── examples/                    # 4 offline demos — run everything with zero keys
├── agents/  skills/  schemas/  contracts/  # workforce defs, skills, contracts
├── docs/                        # blueprint (24 sections), kernel map, agentic-mode, ADRs
└── scripts/verify.mjs           # part verifier (runs in CI)
```

## Status & roadmap

`v0.1.0 — Blueprint + Universal Context Package + Reference Kernel.`

Built **part-by-part**: every part is committed, verified (`scripts/verify.mjs` + offline example runs), and pushed before the next begins. Next up (see [`docs/ROADMAP.md`](docs/ROADMAP.md)):

- [x] Trace replay UI (render any run as a timeline)
- [x] Approval flow demo (human-in-the-loop for ASK verdicts)
- [ ] OpenHands Agent Server adapter (kernel as control plane)
- [x] Evaluation harness + golden tasks (per `docs/evaluation/`)
- [ ] More packs: security, mobile, ML-ops, game-dev

## For contributors

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — part workflow, verifier, commit style
- [`SECURITY.md`](SECURITY.md) — reporting + the repo's own secret-hygiene rules
- CI verifies every push: part integrity, JSON validity, pack/prompt/manifest consistency, Python compile + offline example runs, and secret scanning

## License

Apache-2.0 (see [`LICENSE`](LICENSE)). Reference repositories keep their own licenses — integration guidance in [`docs/references/`](docs/references/README.md).

---

<div align="center">

**If OpenAgent-X saves you tokens, money, or a debugging night — consider dropping a ⭐.**

</div>
