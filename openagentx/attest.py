"""attest — the release attestation: one command, one artifact, every gate.

A release claim that cites five documents is a claim nobody re-checks.
:func:`collect_gates` runs the framework's own gates against one tree and
aggregates them into a single verdict:

- **doctor** — purity + integrity (stdlib-only imports, offline, required
  files, golden tasks valid, workspace writable);
- **audit** — the secret scanner reports ``0 findings``;
- **doctests** — every docstring example in the tree's package is graded
  green (package-mode imports when the root *is* the running package,
  bare-file mode otherwise, so probes are attested by the same rules);
- **manifest** — the tree hashes identically twice (a manifest that will
  not rebuild is a manifest that cannot be checked later);
- **matrix** — every golden-task spec has its prose explainer (the same
  coverage contract the explain view and the verify gate enforce).

Honest contract:

- **a gate that crashes is a red gate** carrying the real exception — the
  attestation itself never crashes on a gate, and never fabricates green;
- **counters, never vibes** — the human render carries counts only (no
  hash, no path, no wall-clock, byte-identical across calls); the machine
  artifact (:func:`artifact_json`) carries the root path and the tree
  hash under ``sort_keys`` so a byte-compare means something;
- **root-parametric** — the same code attests the real repository and any
  probe tree the drills build, one grading path for both;
- **exit contract** — the CLI exits 0 while every gate is green, 1 the
  moment one is red; a planted secret turns the verdict red with the
  file named.

The drill grades this module in a fresh child interpreter (the doctest
gate runs the doctest engine, whose stdout swapping must not race the
eval pool — the same discipline the doctest drill established).

The aggregation logic itself, by example:

>>> _gate("doctor", True, "6/6 checks")["name"]
'doctor'
>>> agg = aggregate([_gate("a", True, "1"), _gate("b", False, "boom")])
>>> agg["ok"], [g["name"] for g in agg["gates"] if not g["ok"]]
(False, ['b'])
>>> aggregate([])
{'gates': [], 'ok': False}
>>> render(aggregate([_gate("doc", True, "6/6 checks")])).splitlines()[0]
'attest: 1 gate — OK'
>>> artifact_json(aggregate([_gate("a", True, "x")])).startswith('{"gates":')
True
"""

from __future__ import annotations

import json
import os

from .audit import run_audit
from .doctor import run_doctor
from .explain import explain_all
from .pack import build_manifest

GATES = ("doctor", "audit", "doctest", "manifest", "matrix")


def _gate(name: str, ok: bool, detail: str, counts: dict | None = None) -> dict:
    """One gate's verdict: name, ok, a human detail line, optional counts."""
    return {"name": str(name), "ok": bool(ok), "detail": str(detail),
            "counts": counts}


def _gate_doctor(root: str) -> dict:
    """Doctor gate: every purity/integrity check must pass."""
    checks = run_doctor(root)
    red = [name for name, ok, _ in checks if not ok]
    detail = f"{len(checks) - len(red)}/{len(checks)} checks"
    if red:
        detail += "; red: " + ", ".join(red)
    return _gate("doctor", not red, detail, {"checks": len(checks)})


def _gate_audit(root: str) -> dict:
    """Audit gate: the secret scanner must report zero findings."""
    findings = run_audit(root)
    if findings:
        named = ", ".join(f"{f['file']}:{f['line']} {f['kind']}"
                          for f in findings[:8])
        detail = f"{len(findings)} findings: {named}"
        if len(findings) > 8:
            detail += f" (+{len(findings) - 8} more)"
    else:
        detail = "0 findings"
    return _gate("audit", not findings, detail, {"findings": len(findings)})


def _gate_doctest(root: str) -> dict:
    """Doctest gate: every docstring example in the tree's package green.

    When the root's ``openagentx/`` directory *is* the running package,
    the gate grades real package imports (relative imports intact);
    otherwise it grades the directory's plain files by the same loaders —
    a foreign package that cannot load standalone is reported as such.
    A tree with no package at all is a loud red, never a skip.
    """
    from .doctests import load_file_modules, load_package_modules, run_doctests

    pkg_dir = os.path.join(root, "openagentx")
    if not os.path.isdir(pkg_dir):
        return _gate("doctest", False, "no openagentx/ package at the root")
    running_pkg = os.path.dirname(os.path.realpath(__file__))
    if os.path.realpath(pkg_dir) == running_pkg:
        loaded = load_package_modules("openagentx")
    else:
        loaded = load_file_modules(pkg_dir)
    report = run_doctests(loaded)
    detail = (f"{report['modules_with_examples']} modules with examples, "
              f"{report['total_examples']} examples, "
              f"{report['total_failed']} failures")
    counts = {"modules": report["total_modules"],
              "with_examples": report["modules_with_examples"],
              "examples": report["total_examples"],
              "failed": report["total_failed"]}
    return _gate("doctest", report["ok"], detail, counts)


def _gate_manifest(root: str) -> dict:
    """Manifest gate: the tree hashes identically twice."""
    m1 = build_manifest(root)
    m2 = build_manifest(root)
    stable = m1 == m2
    detail = (f"{m1['file_count']} files, deterministic rebuild" if stable
              else f"{m1['file_count']} files, UNSTABLE rebuild")
    return _gate("manifest", stable, detail,
                 {"files": m1["file_count"], "tree_sha256": m1["tree_sha256"]})


def _gate_matrix(root: str) -> dict:
    """Matrix gate: every golden-task spec has its prose explainer."""
    tdir = os.path.join(root, "golden_tasks")
    epath = os.path.join(root, "docs", "explainers.md")
    idx = explain_all(tdir, epath)
    expects = 0
    if os.path.isdir(tdir):
        for fname in sorted(os.listdir(tdir)):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(tdir, fname), encoding="utf-8") as fh:
                    spec = json.load(fh)
                expects += len(spec.get("expect", {}))
            except (json.JSONDecodeError, OSError):
                pass  # unreadable specs are already loud rows in the index
    detail = (f"{idx['tasks']} tasks, {idx['with_prose']} with prose, "
              f"{expects} expect keys")
    counts = {"tasks": idx["tasks"], "with_prose": idx["with_prose"],
              "expect_keys": expects}
    return _gate("matrix", idx["ok"], detail, counts)


def aggregate(gates: list) -> dict:
    """Fold gate verdicts into one aggregate; an empty list is never green."""
    return {"gates": list(gates),
            "ok": bool(gates) and all(g["ok"] for g in gates)}


def collect_gates(root: str = ".") -> dict:
    """Run every gate against *root* in fixed order.

    A gate that raises folds into a red gate carrying the real exception
    (the fold IS the contract); the aggregate is green only while every
    gate is green.
    """
    runners = (("doctor", _gate_doctor), ("audit", _gate_audit),
               ("doctest", _gate_doctest), ("manifest", _gate_manifest),
               ("matrix", _gate_matrix))
    gates = []
    for name, fn in runners:
        try:
            gates.append(fn(root))
        except Exception as e:  # noqa: BLE001 — the fold IS the contract
            gates.append(_gate(name, False,
                               f"gate crashed: {type(e).__name__}: {e}"))
    att = aggregate(gates)
    att["root"] = os.path.abspath(root)
    return att


def render(att: dict) -> str:
    """Byte-deterministic render: counters only — no hash, no path, no clock."""
    n_red = sum(1 for g in att["gates"] if not g["ok"])
    verdict = "OK" if att["ok"] else f"FAIL ({n_red} red)"
    label = "gate" if len(att["gates"]) == 1 else "gates"
    lines = [f"attest: {len(att['gates'])} {label} — {verdict}"]
    for g in att["gates"]:
        mark = "OK" if g["ok"] else "RED"
        lines.append(f"  {g['name']:<9} {mark}  {g['detail']}")
    return "\n".join(lines) + "\n"


def artifact_json(att: dict) -> str:
    """The machine artifact: sort_keys JSON, root + tree hash included.

    Two runs over the same tree produce byte-identical artifacts; a
    byte-difference means the tree (or a gate verdict) moved.
    """
    art = {"ok": att["ok"], "root": att.get("root", ""),
           "gates": [{"name": g["name"], "ok": g["ok"], "detail": g["detail"],
                      "counts": g.get("counts")} for g in att["gates"]]}
    return json.dumps(art, sort_keys=True, separators=(",", ":")) + "\n"
