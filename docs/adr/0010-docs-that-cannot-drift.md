# ADR-0010 — Documentation that cannot drift; snippets are executed, not decorative

## Status

Accepted

## Context

Documentation decays silently: an API renames a parameter, a tutorial
snippet stops running, and nothing fails — the docs just start lying.
A repository whose entire discipline is "every green check came from real
behavior" cannot exempt its own prose from that rule.

## Decision

Three mechanisms, added as they were needed. The `required-files` manifest
(`scripts/required-files.txt`, checked by `verify.mjs`) makes deleting a
load-bearing file a loud failure. The docs-sync gate (ADR of S20, part 20)
requires every module in `openagentx/` to have a guide section in
`docs/modules.md`, and lets `docs/tutorial.md` name only real `oax`
subcommands (checked against `cli.py`'s parser set) and only example files
that exist. And by slot discipline, every python and shell snippet in the
tutorial was extracted and executed green before the commit that added it —
the tutorial's snippets are the tests of the tutorial.

## Consequences

Positive: docs fail CI-style instead of lying; onboarding prose is held to
the same bar as drills; renaming a module or subcommand forces the docs
commit in the same breath.

Negative: prose now has a build step (snippet extraction and execution);
some expressive freedom is lost — you cannot write "oax someday-command" in
the tutorial even to dream; ADRs and guides cost maintenance like code,
which is the point.
