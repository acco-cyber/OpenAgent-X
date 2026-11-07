# ADR-0001 — The append-only JSONL journal is the single source of truth

## Status

Accepted

## Context

An agent framework that renders reports from in-memory state invites drift:
the run happened one way, the summary says another, and there is no way to
prove which is true. File formats that rewrite in place (SQLite, pickles)
cannot answer "what exactly happened, in order, including the half-written
moment the process died". Multi-agent runs need one artifact a human can
read and a machine can fold.

## Decision

Every observable fact lands in one append-only JSONL journal per run, as
events with dense sequence numbers 0..n-1 (`events.py`: `Event`, `Journal`,
`read_events`, `read_events_safe`, `sequence_dense`). Nothing else is
truth: replies, counters, reports, dashboards, snapshots — all are derived
folds of the event stream (`trace.replay`, `snapshot.snapshot_at`). The
journal is human-readable JSON per line, one event per line, appended
line-by-line.

A torn tail (a process killed mid-write) is isolated by the safe reader
and reported, never silently dropped; a tear in the middle is a hard
`TornMiddleError` because it means tampering or corruption, not truncation.

## Consequences

Positive: one file tells the whole story for humans and machines; replay is
reproducible on any machine; crashes degrade honestly; every later feature
(views, diffs, snapshots, chains, dashboards) reads the same substrate.

Negative: storage grows with the run (mitigated by `compact`, a lossy
*secondary* representation that never replaces the source); JSONL parsing
is slower than binary formats; writers must never seek or rewrite, which
rules out some "efficient" update patterns on principle.
