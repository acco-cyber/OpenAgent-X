"""Environment doctor — the purity and integrity gate.

Guarantees checked:
- Python >= 3.10
- **stdlib purity**: every import in ``openagentx/*.py`` is stdlib or relative
  (a third-party import fails the doctor — the framework stays dependency-free)
- **offline purity**: no networking modules imported anywhere in the package
- required files present
- golden tasks parse and reference known drills
- workspace writable
"""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile

from .evaluation import DRILLS, list_golden_tasks

NET_MODULES = {"socket", "ssl", "urllib", "http", "ftplib", "telnetlib", "smtplib", "asyncio"}


def _imports_of(path: str):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append(node.module.split(".")[0])
    return sorted(set(out))


def run_doctor(root: str = ".") -> list:
    checks = []
    pkg_dir = os.path.join(root, "openagentx")

    checks.append(("python>=3.10", sys.version_info >= (3, 10),
                   ".".join(map(str, sys.version_info[:3]))))

    nonstdlib, net_imports = [], []
    for f in sorted(os.listdir(pkg_dir)) if os.path.isdir(pkg_dir) else []:
        if not f.endswith(".py"):
            continue
        for mod in _imports_of(os.path.join(pkg_dir, f)):
            if mod not in sys.stdlib_module_names and mod != "openagentx":
                nonstdlib.append(f"{f}:{mod}")
            if mod in NET_MODULES:
                net_imports.append(f"{f}:{mod}")
    checks.append(("stdlib_purity", not nonstdlib, ",".join(nonstdlib) or "pure"))
    checks.append(("offline_purity", not net_imports, ",".join(net_imports) or "offline"))

    missing = []
    req_path = os.path.join(root, "scripts", "required-files.txt")
    if os.path.exists(req_path):
        with open(req_path, encoding="utf-8") as fh:
            for line in fh:
                rel = line.strip()
                if rel and not os.path.exists(os.path.join(root, rel)):
                    missing.append(rel)
        checks.append(("required_files", not missing, ",".join(missing) or "all present"))
    else:
        checks.append(("required_files", False, "scripts/required-files.txt missing"))

    bad_tasks = []
    for p in list_golden_tasks(os.path.join(root, "golden_tasks")):
        try:
            with open(p, encoding="utf-8") as fh:
                t = json.load(fh)
            if not t.get("id") or t.get("drill") not in DRILLS:
                bad_tasks.append(os.path.basename(p))
        except Exception as e:  # noqa: BLE001 — report, never crash doctor
            bad_tasks.append(f"{os.path.basename(p)} ({e})")
    n_tasks = len(list_golden_tasks(os.path.join(root, "golden_tasks")))
    checks.append(("golden_tasks_valid", not bad_tasks,
                   ",".join(bad_tasks) or f"{n_tasks} valid"))

    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".doctor-") as fh:
            fh.write(b"ok")
        writable = True
    except OSError:
        writable = False
    checks.append(("workspace_writable", writable, root))

    return checks
