# Contributing to OpenAgent-X

## Operating rhythm (part-by-part)

This repository grows **one verified part at a time**:

1. Build a small, coherent part.
2. Run `node scripts/verify.mjs` — it must pass.
3. Update `scripts/required-files.txt` if you added required artifacts.
4. Commit with a conventional message (`feat:`, `docs:`, `fix:`, `chore:`).
5. Push and confirm CI is green **before** starting the next part.

## Definition of done for any change

- Documented user/agent outcome and acceptance criteria.
- Typed interfaces and schema validation at boundaries.
- Errors, timeouts, retries and cancellation behavior handled.
- Logs/traces include correlation metadata; secrets redacted.
- Docs updated; license/dependency impact reviewed.
- Change can be disabled safely via configuration or feature flag.

## Engineering conventions

- TypeScript for product code; JSON Schema (draft 2020-12) for contracts.
- Version every agent definition, tool adapter, model alias and event schema.
- Keep business logic out of API route handlers.
- Structured logging with `task_id`, `project_id`, `trace_id`, `actor_id`.
- Unit tests for policy decisions and state transitions; integration tests for runtime behavior.
- Every external integration needs timeout, retry, rate limit, health check, and a license/security review note.

## Branches & PRs

Short-lived feature branches + reviewed PRs; direct pushes to `main` are discouraged once the project has multiple maintainers. Every PR references an issue or acceptance criterion and includes tests, migration impact, and risk notes.

## Licensing notes for contributors

- Do not paste code from reference repositories without recording: repo, version/commit, license, files copied, modifications, obligations (see `docs/references/`).
- MIRA is **AGPL-3.0** — pattern inspiration only; no code reuse without legal review.
- Never commit secrets, tokens, or `.env` values.
