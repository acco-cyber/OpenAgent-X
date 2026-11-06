# Reference: OpenHands

- **Repository:** https://github.com/OpenHands/OpenHands
- **Related:** Software Agent SDK / Agent Server — https://github.com/OpenHands/software-agent-sdk (MIT license file at `software-agent-sdk/blob/main/LICENSE` [R5])
- **Priority in OpenAgent-X:** **P0 — the first (and initially only) coding execution runtime.**

## What OpenAgent-X adopts

| Capability | How it appears in OpenAgent-X |
|---|---|
| Software Agent SDK / Agent Server | The `coding` runtime adapter target: agent execution, workspaces, events, tools, remote execution |
| Workspace lifecycle | Per-task isolated execution instances created/terminated by the adapter (`execution.workspace_created`, `execution.terminated` events) |
| Event streams | Execution events mapped into OpenAgent-X event envelope and appended to the audit ledger |
| Remote execution | Execution-worker pattern: code runs in sandboxed containers/VMs, never in the web UI trust domain |

## What NOT to copy blindly

- **Do not treat the current OpenHands product as one repo with one responsibility.** Its architecture separates Agent Canvas (frontend), SDK/Agent Server, TypeScript client and automation services — verify every package, service and asset separately.
- **Do not embed the entire Agent Canvas into the OpenAgent-X UI** unless integration provides a clear benefit; keep the control-plane UI native.
- **Do not infer the license of all OpenHands services from the SDK's MIT license.**

## Integration pattern (OpenHands-first)

```
OpenAgent-X orchestrator
  │ validates task + permissions; prepares approved task envelope
  ▼
coding runtime adapter (thin)
  1. create/select isolated runtime+workspace
  2. pass AgentTask envelope + artifact references
  3. stream execution events → event ledger
  4. receive artifacts/evidence (diffs, test logs)
  5. schema-check outputs → verification pipeline
  6. terminate or park runtime; confirm cleanup
```

Acceptance (from blueprint §18 H1-011 / W11): the adapter creates/terminates workspaces in an isolated environment; an agent modifies a sample repo and returns a diff plus test log.

## License notes

SDK publishes MIT. Verify each OpenHands package/service/asset independently before reuse; record version/commit and obligations in `THIRD_PARTY_NOTICES`.
