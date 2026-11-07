# ADR-0005 — Golden drills grade real behavior; the harness is honest by construction

## Status

Accepted

## Context

Test suites rot in two directions: checks that exercise fixtures instead of
behavior (the mock tests the mock), and harnesses that hide their own
breakage (a crashed setup reads as "skipped", a regression reads as
"environment issue"). For a framework that sells honesty, a grading
harness that could quietly inflate its own score would be fatal.

## Decision

Grading is a matrix of JSON golden tasks (`golden_tasks/*.json`) run by
`evaluation.py`'s drill registry. Each drill executes real behavior in a
fresh temp workspace: a real `AgentRunner` (or team/fanout/planner runner),
a real journal on disk, real tool executions, real exceptions. Checks are
`Check(name, ok, note)` pairs derived from what actually happened —
replayed events, re-opened journals, re-folded state — never from
fixtures' intentions. Two honesty rules are absolute: a harness error
folds into a failing `harness_error` check (a broken setup can never look
green), and the check count only moves forward (`verify.mjs` enforces the
floor), so nobody can quietly shrink a suite to pass it.

## Consequences

Positive: every green check names an observed fact; the suite doubles as
executable documentation of the contracts; the floor rule makes
regression-of-scope a visible act, not a side effect.

Negative: drills are stricter and slower to write than unit assertions
over internals; refactors must keep event-stream contracts stable or
update drills deliberately (in the open, as real commits); a growing
matrix means growing runtime, which is why `eval` work stays simple and
offline.
