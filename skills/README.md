# Skills Library

Reusable, versioned playbooks agents can load. A skill = **purpose + inputs + steps + tools + verification + budget guidance**. Skills never grant permissions — they operate inside the agent's allowlist and the task's scope.

## Catalog

| Skill | Used by | Purpose |
|---|---|---|
| [web-research](web-research.md) | research | Sourced web investigation with citations and conflict tracking |
| [repo-implementation](repo-implementation.md) | coding | Understand → plan → patch → test in an isolated workspace |
| [data-profiling](data-profiling.md) | data | Profile → pipeline → validate a dataset reproducibly |
| [doc-synthesis](doc-synthesis.md) | writing | Evidence-bound document generation with limitations |

## Skill file contract

```markdown
# skill: <name>
version, used_by, inputs, outputs
steps: ordered, each step naming tools + expected evidence
verification: how the output is checked
budget: recommended token/tool ceilings
failure: what to do when steps fail
```

## Rules

1. Skills are **advisory method**, not authority — permissions stay in the policy service.
2. A skill that needs a tool the agent doesn't have → fail fast with `policy_denial`, don't improvise.
3. Skills record provenance: which skill version produced which artifact.
