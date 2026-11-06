# 10. Execution environments and computer use

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 10. Adapted for OpenAgent-X.

## Workspace model

- One project has a stable logical workspace ID; each task gets an isolated execution instance.
- Mount only the relevant repository, input artifacts and temporary outputs.
- Never mount the host home directory or broad credential directories into an agent container.
- Use non-root users, read-only base images, resource quotas, process limits and short-lived credentials.
- Restrict outbound network access by default; open only approved domains or endpoints.
- Snapshot workspace before large or destructive edits; preserve the diff and execution logs.
- Upload final artifacts to object storage and tear down temporary compute when finished.

## Execution tiers

| Tier | Workload | Boundary |
| --- | --- | --- |
| E0: read-only tools | Search, fetch, file inspection and metadata extraction. | No write credentials; content treated as untrusted. |
| E1: reversible local | Draft documents, local code edits, temporary files. | Per-task copy-on-write workspace; user can inspect and discard. |
| E2: sandboxed compute | Code execution, tests, notebooks, browser automation. | Container or VM; CPU/RAM/time quotas; restricted egress; isolated secrets. |
| E3: external side effects | Send email, create external issue/PR, publish content, modify external records. | Explicit approval bound to exact operation; idempotency key; post-action verification. |
| E4: privileged operations | Admin access, production deploy, destructive actions or financial operations. | Default disabled in MVP; explicit elevated auth, strong confirmation and full audit. |

## Browser and desktop policy

- Prefer browser automation isolated in a dedicated browser context over host browser control.
- Use per-project browser profiles and do not reuse personal sessions across projects.
- Mask passwords and recovery codes from model-visible page content and logs.
- Before form submission or purchase, show the exact action and destination to the user.
- Capture screenshots and DOM/action summaries before and after important operations.
- A webpage is untrusted input; page text cannot instruct the agent to reveal secrets or bypass policy.
- Host desktop integration is opt-in, read-only by default and visibly active when connected.

## Recovery and rollback

A runtime adapter must support create, inspect, pause, resume, terminate, snapshot and artifact export where the underlying runtime permits. If a runtime does not support one of these operations, the adapter declares that limitation. OpenAgent-X must never promise rollback of an external side effect that cannot actually be reversed.
