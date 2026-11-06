# Output contract

A task is complete only when `reply` contains:

1. **Result** — what was done, in one paragraph.
2. **Evidence** — the observations that prove it (file diffs, command exit
   codes, fetched facts). No evidence, no success claim.
3. **Limits** — what was *not* done and why (denied tools, budget stops,
   missing inputs).

If the run stopped early (budget, policy, degeneracy), say so plainly and
report the state you left things in.
