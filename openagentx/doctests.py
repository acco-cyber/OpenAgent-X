"""Per-module docstring self-checks: the examples are graded, not decorative.

Docstring examples rot silently — prose claims code behavior that nothing
executes. This runner closes that gap with the stdlib doctest engine: every
``>>>`` example in every package module's docstrings is executed and graded
each run, so a docstring that lies fails exactly like a drill fails.

Honest contract:

- **every module is reported** — with examples or without; a module with no
  examples is counted and never fabricated green (the drill pins a floor on
  how many examples must exist, so the matrix cannot regress to vacuous);
- **a failing example is loud** — the result carries the doctest log with
  the ``Failed example`` / ``Expected`` / ``Got`` text, not a bare flag;
- **an import failure folds** — a module that raises on import becomes a
  failing result carrying the real exception, never a silent pass;
- **one failure poisons the aggregate** — ``report["ok"]`` is False the
  moment any module fails, exactly like the eval aggregate;
- **byte-deterministic render** — sorted module names, counters only, no
  wall-clock anywhere.

Two loaders feed the same grading path, so probes are graded by the very
code that grades the real tree: :func:`load_package_modules` imports the
installed package (relative imports intact), :func:`load_file_modules`
loads plain ``.py`` files from a directory (the drills' poison probes).
The CLI: ``oax doctest [dir]`` — no argument grades the real package and
exits 0 green / 1 failing; a directory argument grades that directory's
files by the same rules.
"""

from __future__ import annotations

import doctest
import importlib
import importlib.util
import io
import os
import pkgutil

_SKIP = {"__init__", "__main__"}


def load_package_modules(package: str = "openagentx") -> list:
    """Import every real submodule, folding import errors into results.

    Returns an ordered list of ``(module_name, module_or_exception)``;
    the grading path treats an exception exactly like a failing module.
    """
    pkg = importlib.import_module(package)
    loaded = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.name in _SKIP:
            continue
        full = f"{package}.{info.name}"
        try:
            loaded.append((full, importlib.import_module(full)))
        except Exception as e:  # noqa: BLE001 — the fold IS the contract
            loaded.append((full, e))
    return loaded


def load_file_modules(directory: str) -> list:
    """Load plain ``.py`` files from *directory* (probe path).

    Same skip list and same folded-error shape as the package loader, so a
    poisoned or broken file is graded by the same code that grades the
    real tree.
    """
    loaded = []
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".py") or fname[:-3] in _SKIP:
            continue
        path = os.path.join(directory, fname)
        name = f"oax_probe_{fname[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            loaded.append((name, mod))
        except Exception as e:  # noqa: BLE001 — the fold IS the contract
            loaded.append((name, e))
    return loaded


def _one_module(name: str, mod) -> dict:
    """Grade one module's docstring examples with the doctest engine."""
    if isinstance(mod, Exception):
        return {"module": name, "examples": 0, "passed": 0, "failed": 1,
                "ok": False, "log": f"import failed: {type(mod).__name__}: {mod}"}
    finder = doctest.DocTestFinder(exclude_empty=True)
    runner = doctest.DocTestRunner(verbose=False)
    log = io.StringIO()
    tests = finder.find(mod, name=name)
    n_examples = sum(len(t.examples) for t in tests)
    for t in tests:
        runner.run(t, out=log.write)
    summary = runner.summarize()
    failed = int(summary.failed)
    return {"module": name, "examples": n_examples,
            "passed": int(summary.attempted) - failed,
            "failed": failed, "ok": failed == 0, "log": log.getvalue()}


def run_doctests(loaded: list) -> dict:
    """Grade every loaded module; one aggregate, honest edges.

    ``report["ok"]`` is True iff no module failed. Modules without
    examples are reported with ``examples == 0`` — counted, never faked.
    """
    results = [_one_module(name, mod) for name, mod in loaded]
    total_failed = sum(r["failed"] for r in results)
    return {
        "modules": results,
        "ok": total_failed == 0,
        "total_modules": len(results),
        "modules_with_examples": sum(1 for r in results if r["examples"] > 0),
        "total_examples": sum(r["examples"] for r in results),
        "total_failed": total_failed,
    }


def floor_violations(report: dict, min_modules: int = 0,
                     min_examples: int = 0) -> list:
    """Floors the CLI can demand — a shrunk example set is a loud failure.

    Returns human-readable violation messages (empty list = floors met).
    The drill pins the same floors server-side; the flag exists so any
    operator, script or CI can demand the bar without reading the matrix.
    """
    out = []
    if report["modules_with_examples"] < min_modules:
        out.append(f"modules with examples "
                   f"{report['modules_with_examples']} < {min_modules}")
    if report["total_examples"] < min_examples:
        out.append(f"total examples "
                   f"{report['total_examples']} < {min_examples}")
    return out


def render_doctests(report: dict) -> str:
    """Byte-deterministic render: header counts, then one line per module
    with examples, then every failure's log. No wall-clock anywhere."""
    verdict = "OK" if report["ok"] else f"FAIL ({report['total_failed']} failures)"
    lines = [
        f"doctests: {report['total_modules']} modules, "
        f"{report['modules_with_examples']} with examples, "
        f"{report['total_examples']} examples, "
        f"{report['total_failed']} failures — {verdict}",
    ]
    if report["total_examples"] == 0 and report["ok"]:
        lines.append("no docstring examples found — the checker found nothing to grade")
    for r in report["modules"]:
        if r["examples"] > 0:
            lines.append(f"  {r['module']:<28} {r['passed']}/{r['examples']} "
                         f"{'OK' if r['ok'] else 'FAIL'}")
    for r in report["modules"]:
        if not r["ok"]:
            lines.append(f"  --- {r['module']}")
            lines.extend("  " + ln for ln in r["log"].rstrip().splitlines())
    return "\n".join(lines) + "\n"
