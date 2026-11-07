"""explain — the golden matrix explains itself from the CLI.

Every golden task ships a spec (``golden_tasks/<NN-slug>.json``) and a
prose explainer (the ``### <NN-slug>`` section in ``docs/explainers.md``).
:func:`explain_task` joins the two for one task: the machine-readable
contract (drill, task text, script shape, expected keys) and the human
prose (what the run does, what the checks grade, how it fails loudly).
The render is deterministic — no wall-clock, sorted keys, byte-identical
across calls — because a view that drifts is a claim that drifts. A task
without prose is reported honestly (``has_prose: False`` with a loud
line), never papered over: the verify gate forbids that state for golden
tasks, and this view says so.
"""

from __future__ import annotations

import json
import os
import re

EXPLAINERS_PATH = os.path.join("docs", "explainers.md")

_HEAD = re.compile(r"^### (\d{2}-[a-z0-9-]+)[^\S\n]*[^\n]*\n", re.M)
_BODY_STOP = re.compile(r"^(?=#{2,3} )", re.M)


def load_explainers(path: str = EXPLAINERS_PATH) -> dict:
    """Parse docs/explainers.md into {stem: prose-body}; missing file = {}."""
    if not os.path.exists(path):
        return {}
    text = open(path, encoding="utf-8").read()
    out: dict = {}
    heads = list(_HEAD.finditer(text))
    for i, m in enumerate(heads):
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        tail = _BODY_STOP.search(text, start, end)
        body_end = tail.start() if tail else end
        out[m.group(1)] = text[start:body_end].strip("\n")
    return out


def explain_task(task_path: str,
                 explainers_path: str = EXPLAINERS_PATH) -> dict:
    """Join one task spec with its prose explainer; report honestly."""
    with open(task_path, encoding="utf-8") as fh:
        task = json.load(fh)
    stem = str(task.get("id") or os.path.basename(task_path)[:-5])
    script = task.get("script", [])
    expect = task.get("expect", {})
    prose = load_explainers(explainers_path).get(stem)
    return {
        "id": stem,
        "drill": str(task.get("drill", "")),
        "title": str(task.get("title", "")),
        "task_text": str(task.get("task_text", "")),
        "max_steps": int(task.get("max_steps", 0)),
        "script_turns": len(script),
        "expect_keys": sorted(str(k) for k in expect),
        "has_prose": prose is not None,
        "prose": prose,
        "spec_path": str(task_path),
    }


def render_explain(r: dict) -> str:
    """Deterministic, timestamp-free render of one explain report."""
    lines = [
        f"explain {r['id']} (drill: {r['drill']}) — {r['title']}",
        f"task: {r['task_text']}",
        f"spec: {r['spec_path']}"
        f" ({r['script_turns']} script turns, max_steps {r['max_steps']})",
        "expect keys: " + (", ".join(r["expect_keys"]) or "(none)"),
        "",
    ]
    if r["prose"] is not None:
        lines.append(r["prose"])
    else:
        lines.append(
            f"explainer: no prose entry for {r['id']} — every golden task "
            "must have one (the verify gate fails the build without it)")
    return "\n".join(lines).rstrip() + "\n"
    return "\n".join(lines).rstrip() + "\n"


def explain_all(tasks_dir: str = "golden_tasks",
                explainers_path: str = EXPLAINERS_PATH) -> dict:
    """The whole matrix at a glance: every task's prose coverage, honest.

    Rows are sorted by task id (the matrix's own order, spec filenames
    as fallback); a task without prose is a row with ``has_prose: False``
    — the index never fabricates coverage, and the CLI exits 1 while any
    row lacks prose. An unreadable spec is a loud ``error`` row, never a
    silent skip.
    """
    prose_map = load_explainers(explainers_path)
    rows: list = []
    if os.path.isdir(tasks_dir):
        for fname in sorted(os.listdir(tasks_dir)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(tasks_dir, fname)
            try:
                with open(path, encoding="utf-8") as fh:
                    task = json.load(fh)
            except (json.JSONDecodeError, OSError) as e:
                rows.append({"id": fname[:-5], "drill": "",
                             "title": "", "has_prose": False,
                             "error": f"{type(e).__name__}: {e}"})
                continue
            stem = str(task.get("id") or fname[:-5])
            rows.append({"id": stem,
                         "drill": str(task.get("drill", "")),
                         "title": str(task.get("title", "")),
                         "has_prose": stem in prose_map})
    covered = sum(1 for r in rows if r["has_prose"])
    return {"rows": rows, "tasks": len(rows), "with_prose": covered,
            "ok": bool(rows) and covered == len(rows)}


def render_explain_index(idx: dict) -> str:
    """Deterministic, timestamp-free render of the matrix index."""
    verdict = "OK" if idx["ok"] else "PROSE MISSING"
    lines = [
        f"explain --all: {idx['tasks']} tasks, "
        f"{idx['with_prose']} with prose — {verdict}",
    ]
    for r in idx["rows"]:
        mark = "prose" if r["has_prose"] else "NO-PROSE"
        title = r["title"] or ("(unreadable: " + r["error"] + ")"
                               if r.get("error") else "(untitled)")
        lines.append(f"  {r['id']:<22} {r['drill']:<12} [{mark}] {title}")
    return "\n".join(lines) + "\n"
