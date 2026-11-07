# Security Policy

## Supported state

The `main` branch is the only supported state. Fixes land as new commits;
history is never rewritten.

## Reporting a vulnerability

Do **not** open a public issue for a security problem.

Use GitHub's private vulnerability reporting: on this repository's
**Security** tab, choose *Report a vulnerability*. That keeps the report
private between you and the maintainers until a fix is ready.

Please include: what you did, what you expected, what happened, and — because
this project is event-sourced — the journal excerpt that demonstrates it.

## What counts as a vulnerability here

- **Redaction bypass** — a secret reaching the journal, a view, an export
  (report/dashboard/mermaid), or a packed artifact unmasked.
- **Sandbox escape** — a "sandboxed" tool reading, writing, or executing
  outside its declared workdir.
- **Tamper that goes undetected** — an edit, deletion, or reorder of journal
  lines that `verify_journal`, replay, or the diff/property/fuzz stack fails
  to localize or refuse.
- **Purity break** — a non-stdlib import, a network call, or a path by which
  one could enter the package; `oax doctor` and `oax sbom` are the mechanical
  claims.
- **Signature weakness** — a way to make `oax pack2 --check` pass on tampered
  content, or a timing/`key_id` leak beyond the designed surface.
- **Honesty break** — any way to make a drill or gate pass without the
  underlying behavior actually happening.

## What is already in place (and mechanically checked)

- Redaction at the journal boundary, re-applied by every rendered view
  (defense in depth — ADR-0003).
- `oax audit .` — the always-on secret scan of the whole tree (CI gate).
- Opt-in hash-chained journals with edit/deletion/reorder localization
  (ADR-0008).
- Three supply-chain layers: deterministic manifests (`pack`), HMAC-signed
  manifests (`pack2`), structural proofs (`sbom`, `graph`) (ADR-0009).
- The purity gate itself: `doctor` refuses non-stdlib/offline violations
  (ADR-0002).

## Scope notes

- All tokens in fixtures and examples are assembled at runtime by
  concatenation and are not real credentials; a report built on one of them
  cannot be a real leak.
- The package makes no network connections by construction; a "network"
  vulnerability is out of scope unless it is a purity break as above.
- The GitHub Actions workflow consumes no secrets and runs the same gates you
  run locally (`ci.yml`).
