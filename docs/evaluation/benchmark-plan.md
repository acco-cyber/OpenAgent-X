# Evaluation & Benchmark Plan

Adapted from blueprint §19. A serious AI operating system measures the **complete agent workflow**, not only language-model scores. All numbers below are **targets, not achieved results**; publish actual runs with model versions, runtime, hardware, task setup, cost, failures, and confidence intervals.

## Evaluation layers

| Layer | What to measure | Example evidence |
|---|---|---|
| Model | Capability, task accuracy, structured-output validity, tool-call correctness, latency, cost | Provider-specific task sets; schema-validation rate; p50/p95 latency |
| Agent | Subtask completion, tool precision, recovery rate, instruction adherence, artifact quality | Golden agent tasks + independent grading rubric |
| Orchestrator | Plan validity, dependency correctness, state invariants, cancellation and recovery | State-machine tests, replay tests, fault injection |
| Tools/runtime | Success rate, timeout behavior, sandbox-escape attempts, artifact integrity | Tool contract suite, adversarial security suite |
| Memory | Retrieval precision/recall, provenance correctness, stale handling, deletion | Curated query/fact set, access-isolation tests |
| End-to-end | Task success, time-to-completion, user intervention, cost, safety violations | Held-out workflows with documented scoring |

## External benchmark families (use with caution)

| Benchmark | Informs | Caution |
|---|---|---|
| SWE-bench Verified | Real repo issue resolution | Environment/harness/config strongly affect results |
| GAIA | Tool-using multi-step assistant tasks | Leaderboard ≠ product safety or autonomy |
| WebArena | Browser task completion | Site state and automation setup affect reproducibility |
| OSWorld | Computer-use in real apps | High complexity; report resets/failures |
| Terminal-Bench | Terminal/coding agent performance | Record runtime, package cache, timeouts, harness |
| BrowseComp | Hard web research | Document source availability + citation correctness separately |

## Internal suites

- **Planner-100** — 100 hand-authored objectives with expected decomposition, dependencies, acceptance criteria.
- **Tool-50** — 50 read/write tool cases: valid, invalid, denied, timeout, adversarial inputs.
- **Recovery-30** — crash, provider outage, rate limit, workspace failure, cancellation scenarios.
- **Memory-100** — 100 queries with expected source IDs, ACL constraints, stale/conflicting facts.
- **End-to-end-25** — 25 representative workflows across research, coding, data, document generation.
- **Security-red-team** — prompt injection, secret exfiltration, cross-project access, permission-bypass attempts.

## v0.1 targets (not achieved results)

| Metric | Target | Definition |
|---|---|---|
| Provider adapters | 3 reliable at launch; 10+ over time | Adapters pass normalized contract tests incl. streaming/errors |
| Agent profiles | 4 initial; 10 core after stabilization | Each with versioned contract, tests, tool allowlist |
| Task traceability | 100% of completed tasks have event trail + artifact provenance | No orphan completion or unlinked artifacts in release tests |
| Controlled tool success | ≥95% on curated non-adversarial suite | Expected outcome / valid authorized invocation |
| Permission bypass | 0 critical bypasses in release-blocking suite | Any unauthorized P3/P4 action blocks release |
| Recovery | ≥90% of pre-defined recoverable faults recover or fail safely | No silent corruption or duplicate external side effects |
| Memory precision@5 | ≥85% on curated project queries | Authorized relevant sources in top-5; rubric defined pre-run |
| Benchmark reproducibility | 100% of public runs include config/model/runtime/hardware/raw artifact | Run metadata present and immutable |

## Experiment reporting template

1. Hypothesis + primary metric (registered before running).
2. Dataset, task selection, version, licenses, split strategy.
3. Model/provider/version, prompts, routing policy, tool versions.
4. Hardware, driver/runtime versions, container hashes, context settings.
5. Success/failure counts, confidence intervals, cost, latency.
6. Ablations: single vs multi-agent; routed vs fixed model; verifier vs none; memory vs none.
7. Error taxonomy + representative failures.
8. Limitations + any manual intervention.
