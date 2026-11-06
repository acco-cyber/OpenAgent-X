# Reference: Agent Zero

- **Repository:** https://github.com/agent0ai/agent-zero
- **License:** README identifies MIT ([R6]). Review included packages and plugins independently.
- **Priority in OpenAgent-X:** **P2 — optional runtime adapter added after the common agent contract is stable.**

## What OpenAgent-X adopts

| Capability | How it appears in OpenAgent-X |
|---|---|
| Workspace & project isolation | Logical workspace IDs per project; isolated execution instances per task; never mount host home or credential dirs |
| Agent profiles | `AgentDefinition` catalog: versioned, budgeted, allowlisted specialists instead of sovereign personas |
| Plugin/skill patterns | `skills/` format and plugin boundaries with permission ceilings and verification policies |
| A2A/MCP connectivity | MCP for tool interop; A2A-compatible adapter for external agent delegation (translated into AgentTask/AgentResult) |
| Recoverable workspace snapshots | Snapshot before large/destructive edits; RECOVERY state restores from checkpoint artifacts |

## What NOT to copy blindly

- **Do not let Agent Zero become a peer master orchestrator** with independent permissions and memory. It must be wrapped as an optional execution adapter.
- Review bundled plugins/packages individually — MIT for the core does not automatically cover every bundled asset.

## Integration pattern

```
OpenAgent-X orchestrator ──> agent-zero adapter (optional, P2)
  same AgentTask envelope, same permission checks,
  same budgets/timeouts, same verification gates
  outputs flow back as AgentResult + events; nothing bypasses policy
```

## License notes

MIT per README; verify per-package; document version/commit and any bundled-plugin licensing in `THIRD_PARTY_NOTICES`.
