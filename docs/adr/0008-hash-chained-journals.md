# ADR-0008 — Hash-chained journals as an opt-in wrapper; old readers stay welcome

## Status

Accepted

## Context

An append-only journal proves nothing by itself: anyone with write access
can edit a line and re-append. Tamper evidence usually arrives as "switch
to this log format" — breaking every existing reader — or as an external
signature over the whole file, which cannot localize *what* changed.

## Decision

`chain.py` offers `ChainedJournal`, a drop-in `journal_cls` that commits
each line to its predecessor — per-line `{prev, digest}` fields, SHA-256 —
so `verify_journal` localizes any edit, deletion, or reorder to exact
seqs, and `seal` refuses to seal what it cannot verify. The chain fields
ride inside each line as extra keys, invisible to the original readers:
a plain `read_events_safe` still folds a chained journal perfectly, and a
plain journal still "verifies" — reported honestly as `chained: false`.
Torn tails isolate exactly where sealing stopped. Chaos drills attack the
chain (edited lines, reordered lines, splices) and are graded on
localization, not on vibes.

## Consequences

Positive: tamper evidence without a migration; forensic localization (which
seq, not just "something changed"); the honesty rule ("plain journals say
they are plain") keeps the property checkable instead of assumed.

Negative: per-line digests cost write time and bytes; the chain protects
integrity only up to the last verified line — it cannot save an attacker
who rewrites the whole file *and* recomputes the chain (that is what
`pack2`-style external signatures are for); two journal classes is one
more choice contributors must understand.
