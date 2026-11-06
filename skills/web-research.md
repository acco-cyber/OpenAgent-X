# skill: web-research
version: 0.1.0
used_by: [research]
inputs:
  - objective (string, required)
  - constraints: recency window, source-type preferences, exclusions
outputs:
  - sources.json (artifact: url, title, date, publisher, relevance_score)
  - synthesis notes with claims-to-citations map

steps:
  1. decompose the objective into 3-6 research questions; write them down first
  2. search per question (web.search) — 2-3 query variants, not 20; stop when new queries stop returning new domains
  3. fetch candidates (web.fetch); extract metadata (web.extract_metadata); discard paywalled/unfetchable with a note
  4. triage: relevance to question, source class (primary > secondary > aggregator), date within window
  5. keep ≥8 relevant sources or report shortfall honestly in summary
  6. record conflicts between sources; do not resolve silently
  7. synthesize: per question — findings, each claim tagged [S#] to its source

verification:
  - every claim maps to a source id with url + date
  - ≥2 sources for any load-bearing claim
  - date-freshness satisfied per constraints

budget:
  tokens: 60000
  tool_calls: 40

failure:
  - rate-limited (transient_infra): backoff, retry once, then narrow scope
  - sparse results: report the gap in summary with what was tried; never pad with irrelevant sources
