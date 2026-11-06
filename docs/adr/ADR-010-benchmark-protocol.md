# ADR-010: Benchmark protocol and public reporting requirements

**Decision:** Every published run includes config, model/provider/version, prompts, routing policy, tool versions, hardware/runtime, cost, failures and confidence intervals where applicable. Marketing labels are never treated as measured scores. Internal targets are labeled as targets, not results.

**Reason:** Reproducibility and claims discipline are the credibility foundation.

**Consequences:** Benchmark card + limitations ship with releases; failure analysis is published.

**Operational impact:** Run metadata is required and immutable; evaluation suite (Planner-100, Tool-50, Recovery-30, Memory-100, End-to-end-25, Security-red-team) is part of the release process.
