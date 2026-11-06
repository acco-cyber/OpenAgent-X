# Reference: OpenAgent

- **Repository:** https://github.com/the-open-agent/openagent
- **License:** README identifies Apache 2.0 ([R1]). Verify the repo state at integration time.

## What OpenAgent-X adopts (pattern level)

| Capability | How it appears in OpenAgent-X |
|---|---|
| Provider coverage | Broad multi-provider support informs the model-gateway adapter surface (`model-gateway` service), while OpenAgent-X keeps its own capability registry and policy router |
| RAG ingestion | Ingest→chunk→embed→retrieve-with-provenance pipeline shape reused in the memory service data path |
| Browser/shell/office tool patterns | Tool families `research`, `files`, `code`, `data` mirror these patterns with explicit risk classes |
| MCP management | Allowlisted per-project MCP server/tool registry with pinned versions and schema validation |
| Workflow builder | Deferred: task timeline and plan editor first; visual builder only after state semantics are stable (P2) |
| Usage analytics / admin observability | Usage, cost and health telemetry surfaces in the observability stack and Model Control Center screen |

## What NOT to copy blindly

- **Its full agent loop** as a second control plane — OpenAgent-X has exactly one orchestrator.
- **Its provider registry** — OpenAgent-X must own the registry so routing policy, data policy and cost profiles stay canonical.
- **Its workflow engine** — duplication of authority; use the durable workflow layer instead.

## Integration pattern

```
OpenAgent patterns ──(idea-level reuse)──> OpenAgent-X services
  tool surface shapes        ───────────>  tool-gateway (risk-classed families)
  RAG data path              ───────────>  memory-service ingestion pipeline
  analytics views            ───────────>  observability + admin screens
```

## License notes

Apache-2.0 is permissive; code reuse is permissible **after** dependency review and attribution in `THIRD_PARTY_NOTICES`. Default posture: pattern-level adoption; copy code only for narrowly scoped, reviewed utilities.
