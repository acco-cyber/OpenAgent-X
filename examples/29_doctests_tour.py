"""Offline example 29 — oax doctest: the examples are graded, not decorative.

Docstring examples rot silently: prose claims behavior nothing executes.
``oax doctest`` closes that gap with the stdlib doctest engine — every
``>>>`` example in every package module's docstrings is executed and
graded each run, so a docstring that lies fails exactly like a drill
fails. This example walks the checker end-to-end: the real tree graded
green (53 examples across 17 modules), the render proven byte-identical
twice with no wall-clock, a module without examples counted honestly
instead of faked green, a poisoned docstring failing loudly with its
Failed example / Expected / Got log, an import bomb folding into a
failing result carrying the real exception, one failure poisoning the
aggregate, and the CLI agreeing (exit 0 green / 1 failing) — the same
honest contract golden task 40 enforces.
"""

import io
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx import doctests as dt
from openagentx.cli import main as cli_main


def main() -> int:
    # 1) the real tree grades green: every docstring example passes
    report = dt.run_doctests(dt.load_package_modules())
    assert report["ok"] is True, "real tree has failing docstring examples"
    assert report["total_examples"] >= 53, "the example floor regressed"
    assert report["modules_with_examples"] >= 17, "the module floor regressed"
    print(f"[1] real tree green: {report['total_examples']} examples across "
          f"{report['modules_with_examples']} modules, "
          f"{report['total_failed']} failures")

    # 2) every package module is reported — sorted, none skipped
    names = [m["module"] for m in report["modules"]]
    assert names == sorted(names), "module report is not sorted"
    assert all(m["examples"] >= 0 for m in report["modules"])
    zero = [m["module"].split(".")[-1] for m in report["modules"]
            if m["examples"] == 0]
    assert len(zero) > 0, "no-example modules vanished from the report"
    assert all(m["passed"] == 0 and m["failed"] == 0
               for m in report["modules"] if m["examples"] == 0)
    print(f"[2] every module reported; {len(zero)} without examples are "
          f"counted honestly (0 passed, 0 failed — never faked green), e.g. "
          f"{', '.join(sorted(zero)[:3])}")

    # 3) the render is byte-deterministic with no wall-clock
    out = dt.render_doctests(report)
    assert out == dt.render_doctests(report), "render drifted between calls"
    assert re.search(r"\d{10,}", out) is None, "wall-clock leaked into render"
    print("[3] render byte-identical twice, no 10+-digit wall-clock anywhere")

    # 4) a poisoned docstring fails loudly, graded by the real path
    wd = tempfile.mkdtemp(prefix="oax-example29-")
    with open(os.path.join(wd, "poison_doc.py"), "w", encoding="utf-8") as fh:
        fh.write('def add(a, b):\n'
                 '    """Add two numbers.\n\n'
                 '    >>> add(2, 3)\n'
                 '    6\n'
                 '    """\n'
                 '    return a + b\n')
    poison = dt.run_doctests(dt.load_file_modules(wd))
    pm = poison["modules"][0]
    assert poison["ok"] is False and pm["failed"] == 1
    assert "Failed example" in pm["log"] and "Expected:" in pm["log"]
    assert "Got:" in pm["log"] and "5" in pm["log"]
    print("[4] poisoned docstring (promised 6, computed 5) fails loudly; "
          "the log names the example and Expected / Got")

    # 5) an import bomb folds into a failing result with the real exception
    with open(os.path.join(wd, "import_bomb.py"), "w", encoding="utf-8") as fh:
        fh.write('raise RuntimeError("bomb went off")\n')
    bombs = dt.run_doctests(dt.load_file_modules(wd))
    bm = [m for m in bombs["modules"] if m["module"].endswith("import_bomb")][0]
    assert bombs["ok"] is False and bm["ok"] is False
    assert "RuntimeError: bomb went off" in bm["log"]
    print("[5] import bomb folds into a failing result carrying the real "
          "exception — never a silent pass")

    # 6) one failure poisons the aggregate
    combined = dt.run_doctests(
        dt.load_package_modules() + dt.load_file_modules(wd))
    assert combined["ok"] is False and combined["total_failed"] >= 1
    print(f"[6] aggregate poisoned: {combined['total_failed']} failures "
          f"across the combined report — ok is False, no cherry-picking")

    # 7) the CLI agrees: exit 0 green / 1 failing
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc0 = cli_main(["doctest"])
        rc1 = cli_main(["doctest", wd])
    assert rc0 == 0 and rc1 == 1, f"CLI contract broken: {rc0}/{rc1}"
    print("[7] CLI agrees: exit 0 over the real tree, 1 over the poison dir")

    print("OK 29_doctests_tour")
    return 0


if __name__ == "__main__":
    sys.exit(main())
