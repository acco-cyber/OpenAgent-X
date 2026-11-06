# Writing knowledge

## Structure before prose

- One document, one job. State the job in the title and the first two sentences.
- BLUF (bottom line up front): conclusion first, support after, appendix last.
- H2 sections = the reader's questions, in the order they would ask them.
- Paragraphs: 1 idea each, 2–5 sentences; lists for parallel facts, prose for reasoning.

## The four editing passes (run them separately)

1. **Structure** — does the order answer the reader's questions in sequence? Cut or move whole sections.
2. **Clarity** — replace jargon and abstractions with concrete nouns and verbs; split sentences > 25 words.
3. **Honesty** — every claim supported; hedges removed ("might potentially" → "might"); numbers sourced.
4. **Surface** — consistent terminology (one name per thing), tense, formatting, links verified.

## Plain-language rules that survive review

- Active voice by default; passive only when the actor is unknown or irrelevant.
- Define once, use the defined term forever — synonyms confuse technical readers.
- Examples beat descriptions: show a minimal input → output pair.
- Code samples must run as shown; version and environment stated.

## Docs-specific structure

- README: what it is → quickstart (≤5 commands) → how it works → limits → license.
- Every tutorial: numbered steps with expected results after each step ("you should see…").
- Reference docs: complete, exact, ordered for lookup; tutorials: incomplete-but-succeeding paths.

## Agent-specific pitfalls

- Do not pad: length is not thoroughness; cut the summary that repeats the body.
- Match the requested format exactly (tone, length, template) before adding flourishes.
- When facts are missing, mark `[TODO: verify X]` rather than inventing plausible text.
