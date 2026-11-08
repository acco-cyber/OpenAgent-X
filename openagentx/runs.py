"""runs — the multi-run index: a directory of journals, one honest table.

One journal is a run's whole truth; a directory of journals is a
portfolio, and no existing view crosses it — stats, replay, report and
dashboard each look at a single file. :func:`index_runs` scans one
directory and folds every ``*.jsonl`` journal into one deterministic
index, so an operator sees the shape of many runs at once.

Honest contract:

- **one grading path** — every row's counters come from the same
  :func:`stats.run_stats` the single-journal view uses, so the index can
  never disagree with the per-journal view (a second parser would be a
  second source of truth);
- **counters, never payloads** — a journal is raw secrets on disk, so
  the index renders counts and flags only: no payload text, no path
  beyond the file name, no wall-clock anywhere in the human render;
- **torn is a flag, not a filter** — a journal with a torn tail is still
  indexed (its intact prefix counts) and marked ``torn`` in every view;
  a journal torn in the *middle* is a loud error row carrying the real
  exception — never skipped silently;
- **additivity claimed only where true** — events, tool calls, results
  and failures sum across journals; durations do not (the spans overlap),
  so the totals row never carries one;
- **loud emptiness** — a directory with no journals is an honest empty
  index (``ok`` False, exit 1 through the CLI), never fabricated green;
- **determinism** — rows sorted by file name, render byte-identical
  across calls, the machine artifact carries per-row counters under
  ``sort_keys`` (and no directory path, so a byte-compare travels).

The aggregation logic itself, by example:

>>> rows = [{"name": "a.jsonl", "events": 4, "tool_calls": 2,
...          "tool_results": 2, "tool_fails": 1},
...         {"name": "b.jsonl", "events": 3, "tool_calls": 1,
...          "tool_results": 1, "tool_fails": 0}]
>>> totals_of(rows)
{'events': 7, 'tool_calls': 3, 'tool_results': 3, 'tool_fails': 1}
>>> idx = {"journals": 2, "events": 7, "rows": [
...         {"name": "a.jsonl", "events": 4, "steps": 2,
...          "thoughts": 1, "replies": 1, "tool_calls": 2,
...          "tool_results": 2, "tool_fails": 1, "redactions": 1,
...          "torn": False, "dense": True},
...         {"name": "b.jsonl", "events": 3, "steps": 1,
...          "thoughts": 1, "replies": 0, "tool_calls": 1,
...          "tool_results": 1, "tool_fails": 0, "redactions": 0,
...          "torn": True, "dense": True}],
...         "totals": totals_of(rows), "torn": 1, "ok": True}
>>> render_runs(idx).splitlines()[0]
'runs: 2 journals, 7 events — OK (1 torn)'
>>> render_runs(idx).splitlines()[2]
'  b.jsonl          events=3     tools=1/1/0 steps=1 replies=0 redactions=0 dense=True torn'
>>> render_runs({"journals": 0, "events": 0, "rows": [], "totals": {},
...              "torn": 0, "ok": False}).splitlines()[0]
'runs: 0 journals — nothing to index'
>>> bad = {"journals": 1, "events": 0, "torn": 0, "ok": False,
...        "rows": [{"name": "x.jsonl",
...                  "error": "TornMiddleError: journal torn in the middle"}],
...        "totals": {"events": 0, "tool_calls": 0, "tool_results": 0,
...                   "tool_fails": 0}}
>>> render_runs(bad).splitlines()[1].split("ERROR")[1].strip()
'TornMiddleError: journal torn in the middle'
>>> artifact_json(idx).startswith('{"events":7,')
True
"""

from __future__ import annotations

import json
import os

from .stats import run_stats

# The counters that sum across journals; duration is deliberately absent
# (overlapping spans are not additive — claiming it would be a lie).
SUMMED = ("events", "tool_calls", "tool_results", "tool_fails")


def _row(name: str, path: str) -> dict:
    """One journal's index row — counters from the same stats view.

    Raises whatever ``run_stats`` raises (a middle-torn journal raises
    ``TornMiddleError``); the caller folds that into a loud error row.
    """
    st = run_stats(path)
    return {"name": str(name), "events": st["events"],
            "runs_opened": st["runs_opened"],
            "runs_closed": st["runs_closed"], "steps": st["steps"],
            "thoughts": st["thoughts"], "replies": st["replies"],
            "tool_calls": st["tool_calls"],
            "tool_results": st["tool_results"],
            "tool_fails": st["tool_fails"],
            "redactions": st["redactions"],
            "torn": bool(st["torn_tail"]), "dense": bool(st["dense"])}


def totals_of(rows: list) -> dict:
    """Sum the additive counters over *rows*; nothing else is summed.

    Rows that carry an error instead of counters (loud error rows) are
    skipped by the sum — they contributed no events, never a fabricated
    zero.
    """
    return {k: sum(r[k] for r in rows if k in r) for k in SUMMED}


def index_runs(directory: str = ".") -> dict:
    """Index every ``*.jsonl`` journal in *directory*, sorted by name.

    A journal torn in the middle folds into a loud error row carrying
    the real exception; a path that is not a directory raises; an index
    with zero journals (or any error row) is never ``ok``.
    """
    directory = str(directory)
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"runs: {directory} is not a directory")
    rows: list = []
    scanned = 0
    for fname in sorted(os.listdir(directory)):
        path = os.path.join(directory, fname)
        if not fname.endswith(".jsonl") or not os.path.isfile(path):
            continue
        scanned += 1
        try:
            rows.append(_row(fname, path))
        except Exception as e:  # noqa: BLE001 — the fold IS the contract
            # The real exception text, minus the redundant directory
            # prefix: the row's own name column already carries the
            # file, and the render's contract is "no path beyond the
            # file name" — folded, not hidden, and never re-fabricated.
            msg = str(e).replace(str(os.path.abspath(directory)) + os.sep,
                                 "").replace(str(directory) + os.sep, "")
            rows.append({"name": fname,
                         "error": f"{type(e).__name__}: {msg}"})
    totals = totals_of(rows)
    torn = sum(1 for r in rows if r.get("torn") is True)
    ok = bool(rows) and not any("error" in r for r in rows)
    return {"journals": scanned, "events": totals["events"], "rows": rows,
            "totals": totals, "torn": torn, "ok": ok,
            "dir": os.path.abspath(directory)}


def render_runs(idx: dict) -> str:
    """Byte-deterministic render: counters and flags only.

    No payload text, no path beyond the file name, no wall-clock — the
    same journal always renders to the same bytes.
    """
    if not idx.get("journals"):
        return "runs: 0 journals — nothing to index\n"
    torn = idx.get("torn", 0)
    verdict = "OK" if idx.get("ok") else "FAIL"
    tail = f" ({torn} torn)" if torn else ""
    lines = [f"runs: {idx['journals']} journals, {idx['events']} events — "
             f"{verdict}{tail}"]
    for r in idx["rows"]:
        if "error" in r:
            lines.append(f"  {r['name']:<16} ERROR  {r['error']}")
            continue
        mark = " torn" if r["torn"] else ""
        lines.append(f"  {r['name']:<16} events={r['events']:<5} "
                     f"tools={r['tool_calls']}/{r['tool_results']}"
                     f"/{r['tool_fails']} steps={r['steps']} "
                     f"replies={r['replies']} redactions="
                     f"{r['redactions']} dense={r['dense']}{mark}")
    t = idx["totals"]
    lines.append(f"  {'TOTAL':<16} events={t['events']:<5} "
                 f"tools={t['tool_calls']}/{t['tool_results']}"
                 f"/{t['tool_fails']} (durations not summed — "
                 f"spans overlap)")
    return "\n".join(lines) + "\n"


def artifact_json(idx: dict) -> str:
    """The machine artifact: sort_keys JSON — rows, totals, flags.

    Two scans of the same directory produce byte-identical artifacts;
    the directory path is deliberately excluded so a byte-compare
    travels between machines.
    """
    art = {"ok": bool(idx.get("ok")),
           "journals": idx.get("journals", 0),
           "events": idx.get("events", 0),
           "torn": idx.get("torn", 0),
           "rows": idx.get("rows", []),
           "totals": idx.get("totals", {})}
    return json.dumps(art, sort_keys=True, separators=(",", ":")) + "\n"
