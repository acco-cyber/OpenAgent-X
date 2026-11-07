"""Import dependency graph — the package's imports as real structure.

``sbom.py`` classifies every import; ``depgraph.py`` turns the *local*
imports into a directed graph between the package's own modules and
derives the structure honestly:

- **eager vs lazy**: an import at module level (or in a class body)
  runs when the module loads — eager; an import inside a function body
  runs on first call — lazy. CLIs use lazy imports precisely to dodge
  load-order cycles, so the graph records both kinds and never mixes
  them: layering and cycle detection run over the eager edges, and lazy
  edges are reported as the data they are (a lazy cycle among deferred
  imports is expected CLI hygiene, and this graph says so out loud);
- **edges** resolve to modules that actually exist in the package
  (relative ``from .mod import x`` and absolute ``from pkg.mod import x``
  both resolve; anything else is reported ``unresolved``, never hidden);
- **entries** (nothing eagerly imports them) and **leaves** (they
  eagerly import nothing local);
- **layers**: the longest-path level over eager edges — base modules
  sit at layer 0; ``None`` when the eager graph is cyclic;
- **cycles**: strongly connected components over the eager edges, and
  separately over the eager ∪ lazy union, via Tarjan's algorithm;
- **graph_sha256** covers the sorted edge list, so the same package
  always yields the same graph. No timestamps anywhere.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os

from .sbom import build_sbom


def _imports_by_kind(path: str) -> tuple:
    """``(eager, lazy)`` (name, level) pairs of one source file.

    Only crossing into a function body demotes an import to lazy — class
    bodies and module-level ``if``/``try`` blocks still run at load time.
    """
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    eager: list = []
    lazy: list = []

    def visit(node, is_eager: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                names = ([(a.name, 0) for a in child.names]
                         if isinstance(child, ast.Import)
                         else [(child.module or ".", child.level)])
                (eager if is_eager else lazy).extend(names)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, False)
            else:
                visit(child, is_eager)

    visit(tree, True)
    return eager, lazy


def _sccs(nodes: list, succ: dict) -> list:
    """Tarjan's strongly connected components (iterative)."""
    index, low, on_stack = {}, {}, set()
    stack: list = []
    out: list = []
    counter = [0]

    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(succ.get(root, ())))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(succ.get(nxt, ()))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                out.append(sorted(comp))
    return out


def _resolve_edges(root: str, sbom: dict) -> tuple:
    """Resolve local imports to in-package edges; returns (edges, unresolved)."""
    pkg = sbom["package"]
    mod_set = {m["module"] for m in sbom["modules"]}
    edges: list = []
    unresolved: list = []
    seen: set = set()
    for m in sbom["modules"]:
        src_path = os.path.join(root, m["path"])
        eager, lazy = _imports_by_kind(src_path)
        for name, level, kind in [(n, lv, "eager") for n, lv in eager] + \
                                 [(n, lv, "lazy") for n, lv in lazy]:
            if level > 0:  # relative: "." -> the package itself, ".mod" -> pkg.mod
                target = f"{pkg}.{name}" if name not in (".", "") else pkg
            elif name == pkg or name.startswith(pkg + "."):
                target = name  # absolute self-import
            else:
                continue  # stdlib or foreign — not graph material
            if target in mod_set:
                key = (m["module"], target, kind)
                if key not in seen:
                    seen.add(key)
                    edges.append({"from": m["module"], "to": target,
                                  "kind": kind})
            else:
                unresolved.append({"from": m["module"], "import": name})
    edges.sort(key=lambda e: (e["from"], e["to"], e["kind"]))
    unresolved.sort(key=lambda u: (u["from"], u["import"]))
    return edges, unresolved


def build_depgraph(root: str = ".", pkg_dir: str = "") -> dict:
    """Derive the import graph of the package from its own source files."""
    root = os.fspath(root)
    sbom = build_sbom(root, pkg_dir)
    pkg = sbom["package"]
    modules = [m["module"] for m in sbom["modules"]]
    edges, unresolved = _resolve_edges(root, sbom)
    eager = [e for e in edges if e["kind"] == "eager"]

    fan_out = {n: 0 for n in modules}
    fan_in = {n: 0 for n in modules}
    succ: dict = {n: set() for n in modules}
    for e in eager:
        fan_out[e["from"]] += 1
        fan_in[e["to"]] += 1
        succ[e["from"]].add(e["to"])
    succ = {k: sorted(v) for k, v in succ.items()}

    eager_cycles = sorted(c for c in _sccs(modules, succ)
                          if len(c) > 1 or (len(c) == 1 and c[0] in succ[c[0]]))

    all_succ: dict = {n: set() for n in modules}
    for e in edges:
        all_succ[e["from"]].add(e["to"])
    all_succ = {k: sorted(v) for k, v in all_succ.items()}
    lazy_cycles = sorted(c for c in _sccs(modules, all_succ)
                         if len(c) > 1 or (len(c) == 1 and c[0] in all_succ[c[0]]))

    layers = None
    depth = None
    if not eager_cycles:
        memo: dict = {}

        def layer(n: str) -> int:
            if n in memo:
                return memo[n]
            best = 0
            for t in succ[n]:
                best = max(best, layer(t) + 1)
            memo[n] = best
            return best

        layers = {n: layer(n) for n in modules}
        depth = max(layers.values()) if layers else 0

    h = hashlib.sha256()
    for e in edges:
        h.update(f"{e['from']}\t{e['to']}\t{e['kind']}\n".encode("utf-8"))

    entries = sorted(n for n in modules if fan_in[n] == 0)
    leaves = sorted(n for n in modules if fan_out[n] == 0)
    orphans = sorted(n for n in modules if fan_in[n] == 0 and fan_out[n] == 0)

    return {
        "tool": "oax-depgraph",
        "package": pkg,
        "module_count": len(modules),
        "node_count": len(modules),
        "edge_count": len(edges),
        "eager_count": len(eager),
        "lazy_count": len(edges) - len(eager),
        "graph_sha256": h.hexdigest(),
        "stdlib_only": sbom["stdlib_only"],
        "network_modules": sbom["network_modules"],
        "edges": edges,
        "unresolved": unresolved,
        "fan_in": {k: v for k, v in sorted(fan_in.items())},
        "fan_out": {k: v for k, v in sorted(fan_out.items())},
        "entries": entries,
        "leaves": leaves,
        "orphans": orphans,
        "layers": layers,
        "depth": depth,
        "cycles": eager_cycles,
        "lazy_cycles": [c for c in lazy_cycles if c not in eager_cycles],
        "acyclic": not eager_cycles and not unresolved,
    }


def depgraph_json(graph: dict) -> str:
    """Canonical serialization — byte-identical for identical graphs."""
    return json.dumps(graph, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")) + "\n"


def render_depgraph(g: dict) -> str:
    """Deterministic text view: header, eager edges with layers, then the rest."""
    lines = [f"depgraph {g['package']}: {g['node_count']} modules, "
             f"{g['eager_count']} eager + {g['lazy_count']} lazy edges, "
             f"depth={g['depth']} cycles={len(g['cycles'])} "
             f"lazy_cycles={len(g['lazy_cycles'])} "
             f"unresolved={len(g['unresolved'])} "
             f"graph_sha256={g['graph_sha256'][:12]}"]
    for e in g["edges"]:
        if e["kind"] == "eager":
            layer = g["layers"][e["from"]] if g["layers"] is not None else "?"
            lines.append(f"  L{layer} {e['from']} -> {e['to']}")
        else:
            lines.append(f"  LAZY {e['from']} -> {e['to']}")
    for u in g["unresolved"]:
        lines.append(f"  UNRESOLVED {u['from']} -> {u['import']}")
    for c in g["cycles"]:
        lines.append(f"  CYCLE {' <-> '.join(c)}")
    for c in g["lazy_cycles"]:
        lines.append(f"  LAZY-CYCLE {' <-> '.join(c)} (deferred imports)")
    lines.append(f"entries ({len(g['entries'])}): {', '.join(g['entries'])}")
    lines.append(f"leaves   ({len(g['leaves'])}): {', '.join(g['leaves'])}")
    lines.append(f"orphans  ({len(g['orphans'])}): {', '.join(g['orphans'])}")
    return "\n".join(lines) + "\n"
