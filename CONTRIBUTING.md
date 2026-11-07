# Contributing to OpenAgent-X

Thanks for looking under the hood. This repo has one non-negotiable contract:
**everything you claim must be mechanically checkable**. The gates below are
not suggestions — they are the definition of "done".

## The local gate (run all seven before every commit)

```
node scripts/verify.mjs              # required files + golden contracts + docs/README/ADR sync
python3 -m compileall -q openagentx examples
python3 -m openagentx doctor         # purity + integrity gate (6/6)
python3 -m openagentx audit .        # secret scan (0 findings or exit 1)
python3 -m openagentx eval           # the honest golden matrix (all green, count never regresses)
python3 -m openagentx examples       # every offline demo end-to-end
git diff --cached | grep -cE '(ghp_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}|xoxb-|sk-ant-|sk-proj-)'  # must be 0
```

CI runs exactly these gates on Python 3.10 **and** 3.12
(`.github/workflows/ci.yml`) — with zero install steps, because a pure-stdlib
repo needs checkout plus interpreters and nothing else.

## The purity rules

- **Python 3.10+ stdlib only.** No third-party imports, no network modules,
  no async. `oax doctor` fails the build if a non-stdlib import sneaks in.
- **Event-sourced truth.** The journal is the only source of truth; views are
  pure folds of it. Never maintain parallel bookkeeping.
- **Honest grading.** Drills observe real behavior from the run. An exception
  folds into a failing `harness_error` check — never a silent pass, never a
  weakened check.
- **Fixture secrets are assembled at runtime** by concatenation
  (`"ghp_" + "A1b2C3d4E5"*3 + "F9ab12"`-style). A token-shaped literal
  anywhere in the tree is an audit finding and a failed commit.
- **`think` is a tool.** It counts in `expect.tool_calls` and spends budget.
- **Drill workspaces are fresh temp dirs** per invocation; never write into
  the repo during a drill.

## Adding a golden drill

A new drill name must be registered in three places in the same commit:

1. `scripts/verify.mjs` — the drills `Set` (and the shape-set it belongs to).
2. `openagentx/evaluation.py` — the `DRILLS` dict.
3. `golden_tasks/README.md` — the table.

The drill JSON itself needs `id` + `drill` at minimum, and the shape its
drill demands (a `script[]` for runner drills, `hooks.rules[]` for hooks, … —
verify.mjs will tell you exactly what it wants). Eval check count only ever
moves forward.

## Adding or changing docs

Docs cannot drift — the verify gate enforces it:

- every `openagentx/*.py` module must keep its guide in `docs/modules.md`;
- `oax <sub>` mentioned in docs or the README must be a real subcommand;
- every `examples/*.py` and `docs/*.md` reference must resolve;
- eval-scale claims in the README (badge + inline counts) must equal the real
  golden-task count;
- ADR records carry Status / Context / Decision / Consequences and must stay
  indexed in `docs/adr/README.md`.

## Commit style

Small, atomic, real. Every commit contains actual changes; subjects say what
changed and why. During a sprint slot, commits end with the part number
(`— part N (a)`, `(b)`, …, final `— part N`).

## License

By contributing, you agree that your contributions are licensed under the
MIT license that covers this repository.
