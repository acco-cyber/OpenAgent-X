# X-Prompt: layered prompt files

Prompts are **files, not code constants** (the pattern we rated highest in
the reference analysis). Behavior is diffable, overridable, and fork-free.

## Layer precedence (low → high)

1. `prompts/base/` — shipped defaults (this directory)
2. `<packs>/prompts/` — activated knowledge packs may add or override sections
3. `.openagentx/prompts/` — your project's overrides
4. `~/.openagentx/prompts/` — your personal overrides

Higher layers **replace** a section; to **wrap** the default instead of
replacing it, use the include hook anywhere in your override:

```
{{include original}}

Extra rules that apply on top of the default section above.
```

## Section ids and trim priorities

| File | Section | Trim priority (dropped first) |
|---|---|---|
| `10-identity.md` | identity | 3 |
| `20-guardrails.md` | guardrails | 2 |
| `30-protocol.md` | protocol | never (dropped last) |
| `40-output-contract.md` | output | 1 |

The compiler (see `openagentx/prompts.py`) composes visible sections under
the run's token budget: when over budget it replaces the *lowest-value*
sections with one-line stubs — `protocol` and `output` are always kept
intact because a model without the action contract cannot work at all.
