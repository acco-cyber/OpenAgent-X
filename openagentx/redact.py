"""Redaction engine — high-confidence secret patterns, structure-preserving.

``redact()`` rewrites token-shaped substrings in text; ``redact_obj()`` walks
any JSON-able object and rewrites only the *leaves* (dicts keep their keys and
shape, lists keep their order), so redacted payloads stay diffable and
replayable. Every replacement is marked ``[REDACTED:<kind>]`` — the journal
never carries a raw credential, while tools still execute on real values.

Patterns are deliberately high-confidence (well-known token prefixes plus
sufficient entropy) to avoid false positives on ordinary prose.

Example (fixture assembled at runtime, exactly like the drills do):

    >>> raw = "token " + "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    >>> redact(raw)
    ('token [REDACTED:github_token]', 1)
    >>> redact("no secrets here")
    ('no secrets here', 0)
"""

from __future__ import annotations

import re

REDACTED_PREFIX = "[REDACTED:"

PATTERNS: list = [
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(r"xoxb-[A-Za-z0-9-]{10,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai_key", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")),
]


def redact(text: str) -> tuple:
    """Rewrite every high-confidence secret in *text*. Returns (text, count)."""
    s = str(text)
    n = 0
    for kind, pattern in PATTERNS:
        s, k = pattern.subn(f"{REDACTED_PREFIX}{kind}]", s)
        n += k
    return s, n


def redact_obj(obj) -> tuple:
    """Recursively redact leaves of a JSON-able object. Returns (obj, count).

    Dicts keep their keys and structure; lists keep order and length; only
    string leaves whose text matches a pattern are rewritten.
    """
    if isinstance(obj, str):
        out, n = redact(obj)
        return out, n
    if isinstance(obj, dict):
        total = 0
        out: dict = {}
        for k, v in obj.items():
            rv, n = redact_obj(v)
            out[k] = rv
            total += n
        return out, total
    if isinstance(obj, (list, tuple)):
        total = 0
        out = []
        for v in obj:
            rv, n = redact_obj(v)
            out.append(rv)
            total += n
        return (out if not isinstance(obj, tuple) else tuple(out)), total
    return obj, 0
