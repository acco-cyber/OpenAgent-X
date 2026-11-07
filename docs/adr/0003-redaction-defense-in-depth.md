# ADR-0003 — Redaction at the view layer, re-applied everywhere (defense in depth)

## Status

Accepted

## Context

Secrets end up in agent runs: keys pasted into prompts, tokens echoed by
tools, credentials in error text. Filtering at write time is not enough —
the writer can be buggy, the filter can miss a shape, and old journals
already exist. Meanwhile the opposite failure mode is just as bad: an
over-eager filter that mangles non-secret bytes or hides the structure a
debugger needs.

## Decision

`redact.py` rewrites only high-confidence secret shapes (`ghp_…`-style
tokens, AWS `AKIA…`, Slack `xoxb-`, `sk-ant-`/`sk-proj-`) to
`[REDACTED:<kind>]`, preserving the surrounding structure. Redaction is a
*view-layer* contract: reports, stats output, dashboards, mermaid exports
— every rendered surface re-applies redaction to whatever it reads, so a
secret that reached a journal through any accident still cannot reach a
rendered artifact (proven by `golden_tasks/33-dashboard.json` and example
17, which hand-write a runtime-assembled raw token into a journal and
assert both views re-redact it). The repo audits itself: `oax audit .`
scans every file for token-shaped literals and must stay at 0 findings,
so fixtures are assembled at runtime by concatenation.

## Consequences

Positive: the property that matters ("views never leak") holds even when
the journal-writing layer fails; the audit gives a mechanical, always-on
check instead of a policy hope; structure-preserving output stays
debuggable.

Negative: redaction is shape-based — a secret with an unrecognized shape
passes (mitigated by keeping the pattern list high-confidence and by the
audit's independent shape scan); re-redacting every view costs a scan per
render; the `[REDACTED:…]` marker is not reversible by design, which is a
real (intended) loss.
