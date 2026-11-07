# FAQ

Real questions, honest answers — each grounded in how the code actually
behaves.

## Why is everything stdlib-only? Wouldn't pydantic/httpx make this easier?

Yes, and the cost is deliberate (ADR-0002). Every dependency is surface an
auditor must trust without reading. With stdlib only, `oax doctor` proves
the purity mechanically, the SBOM's zero third-party entries is a
checkable claim, and the whole matrix runs anywhere Python 3.10+ runs —
no install, no network. The price: no async, no real model adapters in
the package, and a few small wheels rebuilt by hand.

## Why did my run stop with `budget` instead of finishing?

The tool-call governor (`max_tool_calls`) stopped the loop *before* a call
that would have exceeded the cap. Find the `budget` event in the journal:
it names the rejected tool and shows `used`/`cap`. Executed calls all
precede that line, no reply was fabricated, and the agent's next planned
turn never ran. Raise the cap and the same script finishes (that is
`examples/18_budget_guard.py`'s whole story). Note that `think` is a real
tool — it spends the budget.

## My script has a reply line but the run stopped with `max_steps`. Where did the reply go?

Nowhere — the loop hit its step cap before the model produced the reply.
`max_steps` caps loop turns, not script lines; script exhaustion
(`ScriptExhausted` → `script_error`) and a step cap are different animals.
The journal shows the turns that did happen; the unconsumed script tail
stays unconsumed.

## Why can't I see retries in the journal?

By design (retry): retries are invisible to the journal because the runner
sees one `complete()` — the journal records what happened, not how many
tries it took. Retry bookkeeping (attempts, delays, give-ups) lives on the
retry adapter. If every attempt failed, you get an honest
`RetryExhausted` naming the attempt count; nothing is laundered into a
fake success.

## A cached run and a computed run have identical journals — is the cache lying?

No: the cache sits at the LLM-adapter layer, so the runner journals exactly
what a computed run would journal. The proof is observable outside the
journal: the inner adapter's `.calls` stays put on hits. One changed word
in the prompt changes the SHA-256 key — that is a miss, computed fresh
(`examples/19_cache_hits.py`).

## The audit flagged a token in my test. Why, and what do I do?

`oax audit .` refuses token-shaped literals anywhere in the tree — a test
fixture is still a literal someone might mistake for real. Assemble
fixtures at runtime by concatenation:

```python
tok = "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
```

The scanner cannot see a secret shape in pieces, and the redaction views
will still catch it end to end.

## Can a secret that leaked into a journal reach the dashboard?

No (ADR-0003). Every view re-applies redaction to what it renders. The
drills prove it the hostile way: a raw token is assembled at runtime and
hand-written into a journal, and the dashboard and mermaid exports are
asserted to show `[REDACTED:github_token]` instead.

## Someone edited a line in my journal. How do I prove it?

If it was written by `ChainedJournal`, run `verify_journal(path)`: the
chain commits each line to its predecessor, so an edit, deletion, or
reorder is localized to exact seqs. A plain journal reports `chained:
false` — honestly, it cannot prove anything; that is what chaining is
for (ADR-0008). For whole-file endorsement, sign the tree with `pack2`.

## Two runs of the same script diff as DIFFERENT under `--strict` but SAME otherwise. Which is right?

Both, at different layers: the semantic diff ignores wall-clock `ts`
because two real runs can never share a clock; strict mode compares every
stored byte, and time is bytes there. If they differ beyond `ts` in
semantic mode, something really changed — `diverged_at` names the first
event, and `removed`/`added` carry both tails (`examples/21_replay_diff.py`).

## Why does `validate_schema` reject `True` for an `"integer"` field?

Because in Python, `bool` is a subclass of `int`, and a naive `isinstance`
check waves `True` through as `1`. The lite schema refuses that
confusion on principle: a boolean is not an integer, and a validator that
says otherwise is lying to you (structured).

## Why does the dashboard have no timestamps?

Determinism (ADR-0007): any rendered timestamp makes two renders of the
same file differ, breaking byte-identical output, sha256 fingerprints,
and clean diffs. Duration may appear in the integrity strip or the bench —
reported as wall-clock, never graded. The filesystem knows when a run
happened; the report knows what happened.

## What happens if a run is killed mid-write?

The last, half-written line is a torn tail: the safe reader isolates it,
reports it, and folds the dense prefix; `truncate_torn_tail` restores the
exact pre-tear bytes. A torn line *in the middle* is different — that
raises `TornMiddleError`, because a hole in the sequence means corruption
or tampering, not truncation. The property suite re-checks all of this
after every simulated step.

## How do I add a golden drill?

Copy any task in `golden_tasks/`, give it an id and an existing drill name
(or implement a new drill in `evaluation.py` and register it in `DRILLS`,
the `drills` set in `scripts/verify.mjs`, and the golden README table),
and run `oax eval`. The bar: drills observe real behavior from this run,
harness errors fail loudly, and the total check count never goes down.

## Is any of this graded against a real model?

No — and the docs will not pretend otherwise (ADR-0004). Drills grade the
framework's contracts with deterministic adapters: stop reasons, budgets,
hooks, caches, chains, diffs. Prompt quality and model behavior are out
of scope by construction; a real adapter is one `complete()`
implementation away, and everything upstream already honors the contract.
