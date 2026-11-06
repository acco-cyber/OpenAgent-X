# ADR-009: Source/license policy and third-party notices

**Decision:** Apache-2.0 for OpenAgent-X. Every upstream integration records repository, version/commit, license, files/patterns copied, modifications and obligations in THIRD_PARTY_NOTICES. MIRA (AGPL-3.0): pattern-level inspiration only; no code reuse without legal review.

**Reason:** License conflicts are release blockers; provenance enables clean distribution.

**Consequences:** Contributors cannot paste upstream code without a provenance record.

**Operational impact:** License re-check before every release; SBOM generated for releases.
