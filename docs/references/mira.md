# Reference: MIRA

- **Repository:** https://github.com/Vexillon-ai/MIRA
- **License:** ⚠ **AGPL-3.0** — README explicitly notes network-use source obligations under section 13 for modified network services. **Obtain legal review before any code reuse.** ([R2])

## What OpenAgent-X adopts (pattern level ONLY — no code)

| Capability | How it appears in OpenAgent-X |
|---|---|
| Project/personal memory patterns | Memory domains: task / project / user / knowledge / execution, each with its own access policy |
| Hand-editable wiki | Project memory inspector: search, edit, pin, supersede, export, delete — with provenance and correction controls |
| Multi-channel access | Experience layer web-first; CLI/API/desktop/voice later via the same task API |
| Proactive briefings | Scheduled summaries from task memory — surfaced as candidates, never auto-promoted to durable memory |
| Skills | Versioned skill definitions with allowed tools, budgets and verification requirements (`skills/`) |
| Sandboxing | E0–E4 execution tiers with workspace isolation and snapshots |
| Account-level policy ideas | Identity & policy layer: RBAC roles + ABAC resource sensitivity + signed approvals |

## What NOT to copy blindly

- **Its whole Rust gateway** — OpenAgent-X must not gain a second service boundary with its own auth.
- **Its memory/agent architecture as a core dependency** — would create a second authority for task state, permissions and memory, violating the one-authority rule.

## Integration pattern

```
MIRA behaviors ──(UX/behavior lessons only)──> OpenAgent-X services
  memory domains & wiki UX      ───────────>  memory-service + Project Memory screen
  briefing cadence              ───────────>  orchestrator timers + WAITING_FOR_USER surfaces
  skill packaging               ───────────>  skills/ format (versioned, budgeted, allowlisted)
```

## License notes

AGPL-3.0 section 13: operating a modified network service obligates offering source to network users. **Default posture: zero code reuse.** Borrow behavioral/product ideas only. If code-level reuse is ever proposed: isolate, get counsel review, and document obligations — or redesign natively.
