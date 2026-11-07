# ADR-0007 — Views derive from replay; deterministic bytes, no timestamps

## Status

Accepted

## Context

Once there is more than one summary of a run (text report, HTML report,
stats fingerprint, dashboard), they will disagree — unless every one of
them is a rendering of the same fold. Separately, any rendered timestamp
makes two renders of the same file differ, which breaks caching, diffing,
and the ability to prove "nothing changed" with `sha256`.

## Decision

Every view takes its numbers from `replay` — directly or through
`run_stats`, which itself takes replay's counters. `stats`, `dashboard`,
and `replay` therefore cannot disagree: same file in, same numbers out.
Renders are byte-deterministic: no wall-clock, no dict order, no locale,
no timestamps anywhere in output; integer counts drive bar widths and
percentages (`dashboard.py` derives bars from `int(round(100*count/max))`).
`dashboard_sha256` is a stable fingerprint of the deterministic bytes.
HTML dashboards are self-contained: inline CSS, zero external assets, no
scripts. Wall-clock duration may be *reported* (integrity strip, bench) —
clearly labeled "reported not graded" — because timing is data about the
machine, never a claim about the run's correctness.

## Consequences

Positive: "the dashboard and the stats disagree" is an impossible bug
report; renders diff clean, cache clean, and verify with a hash; the
HTML works offline in any sandbox.

Negative: timestamps are genuinely absent — to know when a run happened
you look at the filesystem, not the report; byte-determinism forbids
convenient-but-unstable output (no random ids, no dict-order accidents),
so every renderer pays attention it would rather not.
