"""Stdlib SBOM — a bill of materials that proves its own purity.

For every module in a package directory the BOM records the sha256 of the
source and its imports classified three ways: ``stdlib`` (top-level module in
``sys.stdlib_module_names``), ``local`` (the package itself or a relative
import), and ``foreign`` (anything else). ``stdlib_only`` is a computed
verdict, not a promise: one foreign import flips it to False. Network modules
(socket, http, ...) are stdlib but reported separately — offline purity is its
own contract. The BOM hash is deterministic over the sorted module entries.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

from .doctor import NET_MODULES


def _classify(tree: ast.AST, pkg: str) -> tuple:
    stdlib, local, foreign = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [(a.name, 0) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or ".", node.level)]
        else:
            continue
        for name, level in names:
            top = name.split(".")[0]
            if level > 0:  # relative import: local by definition
                local.add(name)
            elif top == pkg:
                local.add(name)
            elif top in sys.stdlib_module_names:
                stdlib.add(name)
            else:
                foreign.add(name)
    return sorted(stdlib), sorted(local), sorted(foreign)


def _build_sbom_core(root: str, pdir: str, pkg_name: str,
                     keep_trees: bool = False) -> tuple:
    """Single-parse core shared by ``build_sbom`` and ``build_depgraph``.

    Reads and parses every module exactly once; returns ``(bom, trees)``
    where ``trees`` maps module name to the parsed AST (empty unless
    ``keep_trees``) so a graph build can reuse them instead of re-parsing
    the same sources a second time.
    """
    modules = []
    trees: dict = {}
    for f in sorted(os.listdir(pdir)):
        if not f.endswith(".py"):
            continue
        path = os.path.join(pdir, f)
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src, filename=path)
        stdlib, local, foreign = _classify(tree, pkg_name)
        stem = f[:-3]
        mod = pkg_name if stem == "__init__" else f"{pkg_name}.{stem}"
        modules.append({
            "module": mod,
            "path": rel,
            "sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
            "stdlib_imports": stdlib,
            "local_imports": local,
            "foreign_imports": foreign,
        })
        if keep_trees:
            trees[mod] = tree
    modules.sort(key=lambda m: m["module"])
    h = hashlib.sha256()
    for m in modules:
        h.update(f"{m['module']}\t{m['sha256']}\t{','.join(m['stdlib_imports'])}"
                 f"\t{','.join(m['local_imports'])}\t{','.join(m['foreign_imports'])}\n"
                 .encode("utf-8"))
    bom = {
        "tool": "oax-sbom",
        "algo": "sha256",
        "python": ".".join(map(str, sys.version_info[:3])),
        "package": pkg_name,
        "module_count": len(modules),
        "bom_sha256": h.hexdigest(),
        "stdlib_only": not any(m["foreign_imports"] for m in modules),
        "network_modules": sorted({i for m in modules for i in m["stdlib_imports"]
                                   if i.split(".")[0] in NET_MODULES}),
        "modules": modules,
    }
    return bom, trees


def build_sbom(root: str = ".", pkg_dir: str = "") -> dict:
    """Build the BOM for the package at ``pkg_dir`` (default: ``root/openagentx``)."""
    root = os.fspath(root)
    pdir = pkg_dir or os.path.join(root, "openagentx")
    pkg_name = os.path.basename(os.path.abspath(pdir))
    bom, _trees = _build_sbom_core(root, pdir, pkg_name)
    return bom


def sbom_json(sbom: dict) -> str:
    """Canonical serialization — byte-identical for identical BOMs."""
    return json.dumps(sbom, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")) + "\n"
