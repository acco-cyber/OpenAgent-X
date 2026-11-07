"""Offline example 16 — pack2 + graph: sign the tree, map the package.

``oax pack2`` puts authenticity on top of pack's integrity: the manifest
is signed with HMAC-SHA256 over its canonical bytes, the ``key_id``
names the key without revealing it, and verification reports BOTH
layers — a wrong key or an edited manifest entry fails the signature
while a tampered file fails the content check, and nothing is hidden.

``oax graph`` derives the import dependency graph from source: eager
(module-level) edges build the layers and the cycle detection, lazy
(function-body) edges are recorded as the data they are — the CLI's
real deferred-import ring among cli/doctor/evaluation/sbom shows up in
``lazy_cycles`` without ever tainting the eager layering. A synthetic
eager cycle proves detection; a lazy-only cycle proves the layers
survive deferral.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.depgraph import (build_depgraph, depgraph_json,
                                 render_depgraph)
from openagentx.pack2 import (sign_manifest, signed_json, verify_signature,
                              verify_signed)


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-16-")

    # 1) pack2: sign, verify, then attack both layers
    tree = os.path.join(wd, "tree")
    os.makedirs(tree)
    with open(os.path.join(tree, "hello.txt"), "w", encoding="utf-8") as fh:
        fh.write("payload to sign\n")
    os.makedirs(os.path.join(tree, "sub"))
    with open(os.path.join(tree, "sub", "data.json"), "w", encoding="utf-8") as fh:
        fh.write('{"n": 2}\n')
    key = "oax-" + "demo" + "-signing-key"

    m = sign_manifest(tree, key)
    print(f"pack2: {m['file_count']} files, algo={m['sig']['algo']}, "
          f"key_id={m['sig']['key_id']}")
    ok, probs = verify_signed(tree, m, key)
    if not ok:
        raise SystemExit(f"fresh signature failed: {probs}")

    wrong = verify_signed(tree, m, key + "x")
    if wrong[0] or not any("bad signature" in p for p in wrong[1]):
        raise SystemExit("wrong key did not fail the signature")
    edited = json.loads(signed_json(m))
    edited["files"][0]["sha256"] = "0" * 64
    if verify_signed(tree, edited, key)[0]:
        raise SystemExit("edited manifest still verified")
    with open(os.path.join(tree, "hello.txt"), "a", encoding="utf-8") as fh:
        fh.write("tampered\n")
    tampered = verify_signed(tree, m, key)
    if tampered[0] or not any("modified: hello.txt" in p for p in tampered[1]) \
            or not verify_signature(m, key):
        raise SystemExit("tampered file not isolated to the content layer")
    with open(os.path.join(tree, "hello.txt"), "w", encoding="utf-8") as fh:
        fh.write("payload to sign\n")
    if not verify_signed(tree, m, key)[0]:
        raise SystemExit("restore did not go green")
    print("pack2: wrong key / edited entry / tampered file each fail "
          "their own layer; restore green")

    # 2) graph: the real package's structure, cycles as data
    g = build_depgraph(".")
    print(render_depgraph(g).splitlines()[0])
    if not g["acyclic"] or g["unresolved"]:
        raise SystemExit("eager graph is not clean")
    if g["layers"]["openagentx.events"] != 0 or "openagentx.events" not in g["leaves"]:
        raise SystemExit("base layer wrong")
    if "openagentx.__main__" not in g["entries"] or g["depth"] < 4:
        raise SystemExit("CLI surface not reached")
    if not any("openagentx.cli" in c for c in g["lazy_cycles"]):
        raise SystemExit("the real deferral ring was not reported")
    if depgraph_json(g) != depgraph_json(build_depgraph(".")):
        raise SystemExit("graph not deterministic")
    print(f"graph: eager acyclic, depth {g['depth']}, "
          f"{g['lazy_count']} lazy edges, real deferral ring reported")

    # 3) synthetic: eager cycle kills layers; lazy-only cycle keeps them
    cyc = os.path.join(wd, "cycpkg")
    os.makedirs(cyc)
    open(os.path.join(cyc, "__init__.py"), "w").close()
    with open(os.path.join(cyc, "a.py"), "w", encoding="utf-8") as fh:
        fh.write("from .b import x\n")
    with open(os.path.join(cyc, "b.py"), "w", encoding="utf-8") as fh:
        fh.write("from .a import x\n")
    gc = build_depgraph(wd, cyc)
    if not gc["cycles"] or gc["layers"] is not None:
        raise SystemExit("eager cycle not honestly reported")
    print(f"graph: synthetic eager cycle detected -> {gc['cycles'][0]}, "
          f"layers refused (None)")

    print("OK 16_pack_graph (signatures name their key without revealing it"
          " and both verification layers always report; the import graph"
          " separates eager structure from lazy deferral and reports cycles"
          " as data, never hides them)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
