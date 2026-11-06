# skill: data-profiling
version: 0.1.0
used_by: [data]
inputs:
  - dataset artifact reference
  - analysis questions / target metrics
outputs:
  - profile report (schema, row counts, null rates, distributions, outliers)
  - reproducible pipeline script/notebook
  - validated output artifacts with checksums

steps:
  1. load bounded sample; record schema + dtypes + row counts before anything else
  2. quality: null rates, duplicate keys, impossible values, category cardinality
  3. distributions + correlations for the fields that matter to the objective
  4. propose the minimal pipeline answering the objective; state assumptions (e.g., join keys, filters)
  5. implement as a script/notebook that runs top-to-bottom deterministically
  6. execute under quotas; chunk if needed
  7. validate outputs: result schema, sanity ranges, leakage checks (no target leakage across splits)
  8. upload artifacts with checksums; attach run log

verification:
  - notebook/script reruns from clean state (reproducibility_rerun)
  - output schema matches expected; 0 nulls in key columns where required
  - pipeline version + data snapshot hash recorded

budget:
  tokens: 60000
  tool_calls: 40

failure:
  - quota exceeded (hard_constraint): downsample or chunk; note tradeoff in summary
  - dirty data beyond repair: produce profile + data-quality report as the deliverable; flag BLOCKED for the analysis part
