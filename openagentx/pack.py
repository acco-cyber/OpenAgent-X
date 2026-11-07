"""Deterministic pack manifests — the same tree always yields the same bytes.

``build_manifest()`` hashes every file under a root (bytes, sha256) into a
sorted, timestamp-free manifest; ``manifest_json()`` serializes it canonically
(sort_keys, compact separators) so two builds of an identical tree are
byte-identical. ``verify_manifest()`` recomputes and honestly reports every
missing, modified, or extra file — verification is comparison, never trust.
"""

from __future__ import annotations

import hashlib
import json
import os

from .audit import SKIP_DIRS

MANIFEST_NAME = "pack.manifest.json"
SIGNED_NAME = "pack.signed.json"  # v2 flavor; also never hashes itself


def _sha256_file(path: str) -> tuple:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(65536):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def _iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name in (MANIFEST_NAME, SIGNED_NAME):
                continue  # a manifest never hashes itself (v1 or v2)
            yield os.path.join(dirpath, name)


def _entries(root: str) -> list:
    out = []
    for path in _iter_files(root):
        digest, size = _sha256_file(path)
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        out.append({"path": rel, "bytes": size, "sha256": digest})
    return sorted(out, key=lambda e: e["path"])


def _tree_hash(entries: list) -> str:
    h = hashlib.sha256()
    for e in entries:
        h.update(f"{e['path']}\t{e['bytes']}\t{e['sha256']}\n".encode("utf-8"))
    return h.hexdigest()


def build_manifest(root: str = ".") -> dict:
    """Deterministic manifest of *root*: sorted files, no timestamps."""
    root = os.fspath(root)
    entries = _entries(root)
    return {
        "algo": "sha256",
        "root": os.path.basename(os.path.abspath(root)),
        "file_count": len(entries),
        "tree_sha256": _tree_hash(entries),
        "files": entries,
    }


def manifest_json(manifest: dict) -> str:
    """Canonical serialization — byte-identical for identical manifests."""
    return json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")) + "\n"


def write_manifest(root: str, out: str = "") -> dict:
    """Build a manifest and write it (default: <root>/pack.manifest.json)."""
    m = build_manifest(root)
    path = out or os.path.join(root, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(manifest_json(m))
    return m


def verify_manifest(root: str, manifest: dict) -> tuple:
    """Recompute and compare. Returns (ok, problems) — honest, itemized."""
    problems: list = []
    if manifest.get("algo") != "sha256":
        return False, [f"unsupported algo: {manifest.get('algo')!r}"]
    want = manifest.get("files")
    if not isinstance(want, list):
        return False, ["manifest has no files list"]
    have = _entries(root)
    have_by_path = {e["path"]: e for e in have}
    want_by_path = {e["path"]: e for e in want}
    for path, e in sorted(want_by_path.items()):
        h = have_by_path.get(path)
        if h is None:
            problems.append(f"missing: {path}")
        elif h["sha256"] != e.get("sha256") or h["bytes"] != e.get("bytes"):
            problems.append(f"modified: {path}")
    for path in sorted(set(have_by_path) - set(want_by_path)):
        problems.append(f"extra: {path}")
    if not problems and _tree_hash(have) != manifest.get("tree_sha256"):
        problems.append("tree hash mismatch")
    return (not problems), problems
