# skill: repo-implementation
version: 0.1.0
used_by: [coding]
inputs:
  - objective (string, required)
  - repo artifact reference; acceptance criteria; test expectations
outputs:
  - diff artifact; test log; files-changed summary; dependency-review notes if any

steps:
  1. survey: structure, conventions, existing tests, build tooling (read-only)
  2. locate the minimal change surface; list files likely touched; sanity-check assumptions in summary
  3. snapshot workspace before edits
  4. implement in small commits inside the sandbox; run the narrowest test after each meaningful change
  5. run full deterministic checks: tests, linter, type-check, build — real exit codes
  6. self-diff review: no drive-by changes, no debug leftovers, no secrets in code
  7. emit diff + logs as artifacts

verification:
  - tests pass with persisted logs (not paraphrase)
  - diff scope matches the plan's change surface (± minor)
  - any new dependency carries a review note (license, size, maintenance)

budget:
  tokens: 100000
  tool_calls: 60

failure:
  - tests red after 2 fix cycles (agent_failure): report failing test names + hypothesis; stop
  - change surface bigger than planned: stop, emit partial result, request replan
  - sandbox/tooling error (transient_infra): retry once; then BLOCKED with environment evidence
