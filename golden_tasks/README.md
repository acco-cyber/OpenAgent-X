# Golden tasks

Offline, deterministic evaluation of the agent layer (see
`docs/evaluation/benchmark-plan.md` — "Agent" row). Each `*.json` file is
one scenario; `oax eval` (or `python examples/eval_demo.py`) runs all of
them with zero API keys and writes a reproducible JSON report.

## Format

| Field | Required | Meaning |
|---|---|---|
| `task_id` | ✓ | Stable identifier used in reports |
| `task` | ✓ | The objective handed to the agent |
| `description` | | What the scenario proves |
| `max_iterations` | | Budget ceiling for this run (default 4) |
| `script` | | Model responses replayed in order (last repeats). Omit → EchoLLM behavior. Ends with `{"reply": …}` → clean finish; never replies → budget stops it |
| `include_exec` | | Register shell/python so guardrail tasks can assert *denials* (default false) |
| `expect_status` | | `run.done`, `budget_exceeded`, … (default `run.done`) |
| `expect_min_iterations` / `expect_max_iterations` | | Inclusive bounds on iterations used |
| `expect_tools_used` | | Tools that must be attempted **and** allowed by policy |
| `expect_denials` | | Tools that must be attempted but **never allowed** (deny verdict, or an ask nobody could grant) |
| `expect_reply_contains` | | Substrings (case-insensitive) required in the final reply |
| `expect_budget_stopped` | | Whether the budget/degeneracy guard must stop the run |

Unknown fields are rejected — a typo in an expectation must fail loudly,
not pass silently.

## Adding one

1. Copy an existing task, change `task_id` and the expectations.
2. `python -m openagentx.cli eval` — it must pass offline.
3. Commit it. CI runs the suite on every push.
