# skill: doc-synthesis
version: 0.1.0
used_by: [writing]
inputs:
  - verified artifacts / evidence references (required)
  - format template + audience
outputs:
  - document artifact matching the template
  - consistency checklist result

steps:
  1. inventory the evidence: what is verified fact, what is candidate, what is missing
  2. outline against the template; map every section to its evidence sources
  3. draft with claims tagged to sources; missing evidence → "[needs evidence]" placeholder, never invention
  4. include limitations section: uncertainties, unverified items, manual interventions
  5. run consistency check: no claim without citation; no candidate memory stated as fact
  6. format per template; produce final artifact

verification:
  - evidence_consistency_check passes (every claim ↔ citation)
  - format_completeness_check passes (all template sections present)
  - limitations section present and non-empty

budget:
  tokens: 50000
  tool_calls: 20

failure:
  - evidence insufficient for a required section: deliver with "[needs evidence]" + summary note; do not fabricate
  - template conflict: follow template; note deviation request in warnings[]
