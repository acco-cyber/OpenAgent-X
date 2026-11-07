"""Signed pack manifests v2 — integrity plus authenticity.

``pack.py`` proves *integrity*: the bytes on disk match the manifest.
``pack2`` adds *authenticity*: an HMAC-SHA256 signature over the
canonical manifest bytes. The signature is computed over
``manifest_json()`` of the manifest with the ``sig`` field removed, so
a verifier recomputes exactly the bytes the signer signed. ``key_id``
is the first 12 hex chars of ``sha256(key)`` — it names the key without
revealing it, and two different keys can never collide on a id+digest
pair. Verification is constant-time (``hmac.compare_digest``) and the
failures are honest: a wrong key, an edited manifest entry, or a
tampered file each fail with their own named problem — and the content
check still runs even when the signature is bad, so you learn
*everything* that is wrong, not just the first thing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

from .pack import SIGNED_NAME, build_manifest, manifest_json, verify_manifest

SIG_ALGO = "hmac-sha256"


def derive_key_id(key: str) -> str:
    """Name the key without revealing it: first 12 hex of sha256(key)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _payload(manifest: dict) -> str:
    """The exact bytes the signature covers: canonical core, no sig."""
    core = {k: v for k, v in manifest.items() if k != "sig"}
    return manifest_json(core)


def _sign(key: str, payload: str) -> str:
    return hmac.new(key.encode("utf-8"), payload.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def sign_manifest(root: str, key: str) -> dict:
    """Build the v1 manifest, then sign it — v2 adds the ``sig`` field."""
    m = build_manifest(root)
    m["v"] = 2
    m["sig"] = {
        "algo": SIG_ALGO,
        "key_id": derive_key_id(key),
        "digest": _sign(key, _payload(m)),
    }
    return m


def verify_signature(manifest: dict, key: str) -> bool:
    """Constant-time check of the HMAC over the canonical core bytes."""
    sig = manifest.get("sig")
    if not isinstance(sig, dict) or sig.get("algo") != SIG_ALGO:
        return False
    return hmac.compare_digest(str(sig.get("digest", "")),
                               _sign(key, _payload(manifest)))


def verify_signed(root: str, manifest: dict, key: str) -> tuple:
    """Signature first, then content — both reported, never short-circuited."""
    problems: list = []
    if not isinstance(manifest.get("sig"), dict):
        problems.append("unsigned manifest (no sig field)")
    elif not verify_signature(manifest, key):
        problems.append("bad signature (wrong key or edited manifest)")
    core = {k: v for k, v in manifest.items() if k != "sig"}
    content_ok, content_problems = verify_manifest(root, core)
    problems.extend(content_problems)
    return (not problems), problems


def signed_json(manifest: dict) -> str:
    """Canonical serialization including the sig field (sorted keys)."""
    return json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")) + "\n"


def write_signed(root: str, key: str, out: str = "") -> dict:
    """Sign ``root`` and write the signed manifest next to it by default."""
    m = sign_manifest(root, key)
    path = out or os.path.join(root, SIGNED_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(signed_json(m))
    return m
