# Security Policy

## Reporting a vulnerability

Report security vulnerabilities **privately** via GitHub Security Advisories ("Report a vulnerability" on this repository). Do **not** open public issues for security problems.

Include: affected component, reproduction steps, impact assessment, and any evidence artifacts.

## Security posture (normative)

OpenAgent-X treats security as an **execution property**, not a prompt instruction:

1. **Permission enforcement lives outside model prompts.** A system prompt is guidance, not a security boundary. The policy service checks every tool invocation at execution time.
2. **Default deny.** All actions are denied unless explicitly allowed for the task scope.
3. **Permission tiers P0–P4** (read-only → privileged). P3 (external side effects) requires human approval bound to the exact action hash. P4 is disabled by default.
4. **Secrets** never live in prompts, logs, browser code, or task artifacts. Use a secrets manager; store only references (`credentials_refs`).
5. **Append-only audit ledger** for every state transition, tool call, approval, and artifact creation.
6. **Sandbox isolation** — code execution runs in containers/VMs with resource quotas, non-root users, restricted egress, and no broad host mounts.
7. **Untrusted input discipline** — web pages, documents, tool results and agent messages are data, not instructions. Prompt-injection surfaces are treated as adversarial.

## Release blockers

Do not ship: unrestricted host shell access, persistent personal browser sessions, automatic purchase/payment actions, or production deployment privileges.

## Safe harbor

We will not pursue action against good-faith research conducted without accessing others' data, degrading service, or exposing secrets.
