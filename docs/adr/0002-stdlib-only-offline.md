# ADR-0002 — Pure standard library only, offline by construction

## Status

Accepted

## Context

Agent frameworks routinely accrete dependencies: an HTTP client here, a
pydantic model there, a vector store somewhere else. Each dependency is a
supply-chain risk, a versioning obligation, and — for anyone auditing the
code — more surface they must trust without reading. A framework whose
selling point is auditability cannot ask auditors to also audit its
dependency tree.

## Decision

OpenAgent-X runs on the Python 3.10+ standard library alone. No
third-party imports, no network modules, ever — enforced by `doctor`
(checks `stdlib_purity` and `offline_purity`, 6/6 to pass) and proven by
`sbom` (a bill of materials whose zero third-party entries is a checkable
claim) and `depgraph` (every import resolved and classified eager or lazy).
`oax eval`, `oax examples`, and every golden drill run fully offline:
LLMs are scripted adapters, tools are sandboxed builtins, workspaces are
fresh temp dirs.

## Consequences

Positive: `pip install` is a formality (there is nothing to install);
audits read one tree with no transitive surprises; the eval matrix is
deterministic byte-for-byte and runs anywhere Python runs; no dependency
can phone home because nothing in the package can.

Negative: no real HTTP model adapters (an integration would live outside
the package and be someone's explicit choice); no async runtime — loops
are sequential, and fanout branches are simulated concurrency on real
separate journals, not threads; some wheels get reinvented small (a JSON
repair pass instead of a library).
