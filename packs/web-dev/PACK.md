# Web development knowledge

## Architecture defaults (when the task does not specify)

- Framework-first: use the project's existing stack; do not introduce a new one.
- Server logic in route handlers / backend APIs; client components only for interactivity.
- One concern per component; compose, do not nest god-components.
- State: server state from APIs with caching; local UI state minimal; no duplicated sources of truth.

## Performance checklist (apply before claiming done)

- Images: explicit dimensions, lazy-loading below the fold, modern formats.
- No layout shift: reserve space for async content (skeletons, aspect ratios).
- Long lists: windowing or pagination above ~100 rows.
- Bundle discipline: no full-library imports for one function; code-split routes.
- Waterfalls: parallelize independent fetches; cache repeated ones.

## Security checklist (never skip)

- Never trust client input: validate and sanitize server-side, every time.
- Secrets only in server-side env — never in client bundles, never in git.
- Escape rendered user content; prefer frameworks' auto-escaping over `dangerously*` APIs.
- AuthZ on the server per request; client checks are UX, not security.
- Set security headers: CSP, X-Content-Type-Options, Referrer-Policy, frame options.

## Responsive & accessibility (non-negotiable)

- Mobile-first breakpoints; test 360px, 768px, 1280px widths.
- Touch targets ≥ 44px; visible focus states; keyboard-complete flows.
- Semantic HTML (nav/main/section); alt text for images; labels for inputs.
- Footer sticks to viewport bottom on short pages; pushes down naturally on long pages.

## Testing ladder (evidence before claims)

1. Renders without errors (build/compile passes).
2. Golden path works end-to-end (click → action → visible result).
3. Empty, loading, and error states render for every async view.
4. Responsive holds at the three widths; no horizontal overflow.

## Agent-specific pitfalls

- Do not "fix" hydration mismatches by silencing warnings — find the divergence.
- Do not add client-side data fetching where server components already stream it.
- Prefer editing existing files over creating parallel copies of components.
