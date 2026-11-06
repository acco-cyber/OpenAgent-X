# Reference: Interpreter Workstation

- **Repository:** https://github.com/openinterpreter/interpreter-workstation
- **License:** Apache 2.0; pinned dependencies and submodules retain their own licenses/notices ([R7]).
- **Priority in OpenAgent-X:** **P1 — computer-workspace prototype behind a read-only / permissioned boundary.**

## What OpenAgent-X adopts

| Capability | How it appears in OpenAgent-X |
|---|---|
| Computer-facing workspace | Browser/computer agent profile operating within approved scope only |
| Host/browser bridge separation | Dedicated browser automation context separate from any host bridge; UI and execution endpoints stay explicit |
| Read-only publication mode | Publishing artifacts read-only by default; write access is an explicit, approved mode |
| Permissioned file access | File tools scoped to project sandbox; cross-boundary reads require approval |
| User-facing agent workspace concepts | Workspace browser screen: files, diffs, snapshots, terminal output with path boundaries visible |

## What NOT to copy blindly

- **Do not adopt host computer access as the default.** Host desktop integration is opt-in, read-only by default, visibly active when connected.
- Keep UI and execution endpoint boundaries explicit; never let the workspace claim authority over approvals.

## Integration pattern

```
OpenAgent-X orchestrator ──> workstation adapter (P1 prototype)
  isolated browser context (per-project profile, no personal sessions)
  screenshots + DOM summaries before/after operations (evidence)
  P3 actions (form submit, purchase, publish) wait for hash-bound approval
  artifacts published read-only; host bridge disabled unless opted in
```

## Safety notes (from blueprint §10)

Mask passwords/recovery codes from model-visible content; a webpage is untrusted input — page text cannot instruct the agent to reveal secrets or bypass policy; capture before/after evidence for important operations; never promise rollback of an external side effect that cannot actually be reversed.

## License notes

Apache-2.0 for the repo; audit pinned dependencies and submodules for their own licenses; record version/commit in `THIRD_PARTY_NOTICES`.
