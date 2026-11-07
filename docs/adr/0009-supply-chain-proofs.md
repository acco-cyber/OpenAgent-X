# ADR-0009 — Supply-chain proofs: deterministic manifests, then signatures, then structure

## Status

Accepted

## Context

"Here is what I ship" claims are unverifiable without mechanics: a file
listing with timestamps proves nothing (the same tree hashes differently
an hour later), a checksum proves content but not who endorsed it, and
import lists rot the moment someone adds a lazy import inside a function.

## Decision

Three layers, each buildable and checkable offline. First, deterministic
manifests (`pack.py`): sorted entries, per-file SHA-256, a tree hash over
the canonical manifest bytes — the same tree always yields the same
bytes, so a manifest is a fingerprint of content, not of the clock.
Second, authenticity on top (`pack2.py`): HMAC-SHA256 over the canonical
sig-stripped manifest, `key_id` naming the key without revealing it,
constant-time verification, and both layers (content + signature) always
reporting so a tampered file fails only the content layer while the
signature stays green. Third, structural truth (`sbom.py`, `depgraph.py`):
a stdlib bill of materials whose zero third-party entries is a checkable
purity claim, and an import graph with eager edges building longest-path
layers (Tarjan cycle detection) while lazy function-body edges are
reported as data without tainting the layering.

## Consequences

Positive: every claim in the chain ("these bytes", "this key endorsed
them", "nothing impure is imported") has a mechanical check and an exit
code; layering failures are named, not inferred.

Negative: determinism forbids convenience (manifests must sort and
normalize aggressively); HMAC needs key management the framework
deliberately does not provide; the eager/lazy split makes some real
imports visible as "lazy" without changing behavior, which readers must
learn to interpret.
