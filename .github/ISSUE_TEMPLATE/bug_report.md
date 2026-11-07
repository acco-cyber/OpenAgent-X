---
name: Bug report
about: Something the journal shows is not something the code claims
labels: bug
---

A bug here is a broken contract, so please show the contract failing.

**What happened**

A clear, factual description. If a check went green when it should not have
(or red when it should not have), say so explicitly.

**Reproduction**

The exact commands and, where relevant, the scripted turns:

```
python3 -m openagentx run turns.jsonl --task "..." --workdir demo-wd --timeline
```

Attach the journal excerpt (JSONL) that demonstrates the behavior — the
journal is the truth, so the bug should be visible in it.

**Environment**

- OS:
- Python version (`python3 --version`):
- Commit (`git rev-parse HEAD`):

**Gate output**

```
python3 -m openagentx doctor
python3 -m openagentx audit .
python3 -m openagentx eval
```

Paste the relevant lines. If doctor/audit/eval pass but the behavior still
contradicts the docs, that is exactly the bug to report (docs cannot drift is
a gate; reality drifting from docs is the bug behind it).

**Expected vs actual**

What the docs/ADR/README promise, and what the journal shows instead.
