# Architecture Decision Records

Ten records, one per load-bearing decision. Each states the context that
forced it, the decision itself, and the honest consequences — including
the costs. Status is `Accepted` for all; superseding a record means a new
record that names its predecessor, never a silent edit.

| # | Record | Decision in one line |
| --- | --- | --- |
| [0001](0001-journal-is-the-truth.md) | The journal is the truth | Append-only JSONL events, dense seqs; everything else is a derived fold |
| [0002](0002-stdlib-only-offline.md) | Stdlib only, offline | Pure Python 3.10+ stdlib, enforced by doctor, proven by sbom/depgraph |
| [0003](0003-redaction-defense-in-depth.md) | Redaction everywhere | High-confidence shapes rewritten at every view; the repo audits itself |
| [0004](0004-scripted-adapters.md) | Scripted adapters | Deterministic offline LLMs as the default; the adapter is the boundary |
| [0005](0005-honest-golden-drills.md) | Honest drills | Golden tasks grade real behavior; harness errors fail; counts only grow |
| [0006](0006-stop-reasons-control-plane.md) | Stop semantics | Four stop reasons; stop/handoff are control-plane, never tool calls |
| [0007](0007-views-from-replay.md) | Views agree | All views render replay's numbers; byte-deterministic, zero timestamps |
| [0008](0008-hash-chained-journals.md) | Tamper evidence | Opt-in per-line hash chains; old readers unaffected, edits localized |
| [0009](0009-supply-chain-proofs.md) | Supply-chain proofs | Deterministic manifests → signatures → structural SBOM + depgraph |
| [0010](0010-docs-that-cannot-drift.md) | Docs cannot drift | Manifest + docs-sync gate + executed snippets keep prose honest |
