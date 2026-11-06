# 19. Evaluation, benchmarking and reliability targets

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 19. Adapted for OpenAgent-X.

## Evaluation philosophy

A serious AI operating system needs an evaluation system that measures the complete agent workflow, not only language model benchmark scores. Benchmarks are selected by capability; none of the proposed targets below is a measured result. Publish actual runs with model versions, runtime, hardware, task setup, cost, failures and confidence intervals where applicable.

## Evaluation layers

| Layer | What to measure | Example evidence |
|-------|-----------------|------------------|
| Model | Capability, task accuracy, structured-output validity, tool-call correctness, latency and cost. | Provider-specific task sets; schema-validation rate; p50/p95 latency. |
| Agent | Subtask completion, tool precision, recovery rate, instruction adherence and artifact quality. | Golden agent tasks and independent grading rubric. |
| Orchestrator | Plan validity, dependency correctness, state invariants, cancellation and recovery. | State-machine tests, replay tests, fault injection. |
| Tools / runtime | Success rate, timeout behavior, sandbox escape attempts, artifact integrity. | Tool contract suite, adversarial security suite, runtime tests. |
| Memory | Retrieval precision/recall, provenance correctness, stale-memory handling and deletion. | Curated query/fact set and access-isolation tests. |
| End-to-end product | Task success, time-to-completion, user intervention, cost, safety violations and satisfaction. | Held-out workflows with documented scoring criteria. |

## Relevant external benchmark families

| Benchmark | What it informs | Use caution |
|-----------|-----------------|-------------|
| SWE-bench Verified | Real repository issue resolution and code change capability. | Environment, harness and model agent configuration strongly affect results. [R16] |
| GAIA | General assistant tasks that require tool use and multi-step reasoning. | Do not equate leaderboard score with product safety or broad autonomy. [R17] |
| WebArena | Browser-based web task completion. | Website state and browser automation setup affect reproducibility. [R18] |
| OSWorld | Computer-use tasks in real applications and operating systems. | High execution complexity; isolate the environment and report resets/failures. [R19] |
| Terminal-Bench | Terminal and coding agent performance. | Record runtime, package cache, timeouts and agent harness. [R20] |
| BrowseComp | Web research and information retrieval under difficult conditions. | Document source availability and citation correctness separately. [R21] |

## Internal benchmark suite

- Planner-100: 100 hand-authored objectives with expected decomposition, dependencies and acceptance criteria.
- Tool-50: 50 read/write tool cases covering valid, invalid, denied, timeout and adversarial inputs.
- Recovery-30: process crash, provider outage, rate limit, workspace failure and cancellation scenarios.
- Memory-100: 100 queries with expected source IDs, ACL constraints and stale/conflicting facts.
- End-to-end-25: 25 representative workflows across research, coding, data and document generation.
- Security-red-team: prompt injection, secret exfiltration, cross-project access and permission-bypass attempts.

## Proposed v0.1 targets (not achieved results)

| Metric | Proposed target | Measurement definition |
|--------|-----------------|------------------------|
| Provider adapters | 3 reliable providers at launch; 10+ over time. | Adapters pass normalized contract tests, including streaming and errors. |
| Agent profiles | 4 initial profiles; 10 core profiles after stabilization. | Each has versioned contract, tests and tool allowlist. |
| Task traceability | 100% of completed tasks have event trail and artifact provenance. | No orphan task completion or unlinked artifacts in release tests. |
| Controlled tool success | >=95% in the curated non-adversarial tool suite. | Successful expected outcome / valid authorized test invocation. |
| Permission bypass | 0 critical bypasses in release-blocking security suite. | Any unauthorized P3/P4 action is a release blocker. |
| Recovery | >=90% of pre-defined recoverable fault cases recover or fail safely. | No silent data corruption or duplicate external side effects. |
| Memory precision@5 | >=85% on curated project retrieval queries. | Relevant authorized sources in top five / all returned top-five sources; define scoring rubric before run. |
| Benchmark reproducibility | 100% of public runs include config, model, runtime, hardware and raw result artifact. | Required run metadata is present and immutable. |

## Experiment reporting template

- Hypothesis and primary metric, registered before running the experiment.
- Dataset, task selection, version, licenses and split strategy.
- Model/provider/version, prompts, routing policy and tool versions.
- Hardware, driver/runtime versions, container hashes and context settings.
- Success/failure counts, confidence intervals where appropriate, cost and latency.
- Ablations: single agent vs multi-agent, model routing vs fixed model, verifier vs no verifier, memory vs no memory.
- Error taxonomy and representative failure cases.
- Limitations and any manual intervention.
