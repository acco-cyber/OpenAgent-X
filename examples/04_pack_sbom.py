"""Offline example 04 — packs & SBOM: tamper is detected, purity is computed.

A scratch tree gets a deterministic manifest; the verifier is green until the
tree is touched, then reports exactly what changed (modified / extra /
missing) and goes green again after restore. The SBOM proves the framework
is stdlib-only — as a computed verdict, not a promise.
"""

import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.pack import build_manifest, manifest_json, verify_manifest, write_manifest
from openagentx.sbom import build_sbom


def main() -> int:
    # --- pack: deterministic manifest + honest verification -----------------
    wd = tempfile.mkdtemp(prefix="oax-example-04-")
    with open(os.path.join(wd, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("alpha payload\n")
    os.makedirs(os.path.join(wd, "sub"))
    with open(os.path.join(wd, "sub", "b.txt"), "w", encoding="utf-8") as fh:
        fh.write("beta payload\n")
    manifest = write_manifest(wd)
    assert manifest_json(build_manifest(wd)) == manifest_json(manifest), \
        "rebuilds must be byte-identical"
    ok, problems = verify_manifest(wd, manifest)
    assert ok and problems == [], problems

    with open(os.path.join(wd, "a.txt"), "a", encoding="utf-8") as fh:
        fh.write("tampered\n")
    ok, problems = verify_manifest(wd, manifest)
    assert not ok and problems == ["modified: a.txt"], problems

    with open(os.path.join(wd, "a.txt"), "w", encoding="utf-8") as fh:
        fh.write("alpha payload\n")
    with open(os.path.join(wd, "extra.txt"), "w", encoding="utf-8") as fh:
        fh.write("sneaky\n")
    ok, problems = verify_manifest(wd, manifest)
    assert not ok and problems == ["extra: extra.txt"], problems
    os.remove(os.path.join(wd, "extra.txt"))

    entry = next(e for e in manifest["files"] if e["path"] == "a.txt")
    assert entry["sha256"] == hashlib.sha256(b"alpha payload\n").hexdigest()
    print(f"pack: {manifest['file_count']} files tree_sha256={manifest['tree_sha256'][:16]}…")

    # --- sbom: the purity verdict is computed, not promised ------------------
    repo = os.path.join(os.path.dirname(__file__), "..")
    sbom = build_sbom(repo)
    assert sbom["stdlib_only"] is True, "the framework must be stdlib-only"
    assert sbom["network_modules"] == [], "no network modules, ever"
    assert all(len(m["sha256"]) == 64 for m in sbom["modules"])
    assert any(m["module"] == "openagentx.__main__" for m in sbom["modules"])
    print(f"sbom: {sbom['module_count']} modules stdlib_only={sbom['stdlib_only']} "
          f"bom_sha256={sbom['bom_sha256'][:16]}…")
    print("OK 04_pack_sbom (deterministic manifest, tamper detected, computed purity)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
