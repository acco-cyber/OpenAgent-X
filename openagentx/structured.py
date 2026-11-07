"""Structured output: repair messy LLM JSON, validate against a lite schema.

Real model replies rarely arrive as pristine JSON: markdown fences, trailing
commas, Python literals, smart quotes and surrounding prose all show up.
:func:`parse_json_loose` applies a deterministic, ordered repair pipeline and
reports exactly which repairs fired — the repair notes are part of the
honest answer, never hidden. Unparseable input raises ``ValueError``; it is
never silently coerced to ``{}`` or ``None``.

:func:`validate_schema` checks a parsed value against a small JSON-Schema
subset (``type`` / ``required`` / ``properties`` / ``items`` / ``enum``) and
returns a list of human-readable errors with ``$.a.b[0]`` paths. Empty list
means valid. Note the sharp edge it gets right: ``True`` is NOT an integer.

Example (fenced JSON is recovered; the bool-for-integer edge is kept sharp):

    >>> parse_json_loose('```json\\n{"a": 1}\\n```')
    ({'a': 1}, ['fences'])
    >>> validate_schema({"a": 1}, {"type": "object", "properties": {"a": {"type": "number"}}})
    []
    >>> validate_schema(True, {"type": "integer"})
    ['$: want integer, got bool']
"""

from __future__ import annotations

import json
import re

TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _fix_smart_quotes(s: str) -> str:
    return (s.replace("\u2018", "'").replace("\u2019", "'")
             .replace("\u201c", '"').replace("\u201d", '"'))


def _strip_fences(s: str) -> str:
    out = re.sub(r"(?m)^\s*```[a-zA-Z0-9]*\s*$\n?", "", s)
    return out.strip()


def _fix_literals(s: str) -> str:
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "null", s)
    return s


def _fix_trailing_commas(s: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", s)


def _extract_balanced(s: str) -> str:
    """Slice the first balanced ``{...}`` or ``[...]`` block (string-aware)."""
    opener = None
    start = -1
    for i, c in enumerate(s):
        if c in "{[":
            opener, start = c, i
            break
    if opener is None:
        return s
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0 and c == closer:
                return s[start:i + 1]
    return s  # unbalanced: leave unchanged, parse attempt will fail


# Ordered repair pipeline. Each pass fires at most once per note; two rounds
# let a later pass (extract) benefit from earlier repairs applied to the
# extracted slice, e.g. prose + braces + trailing comma + Python literal.
PASSES = (
    ("smart_quotes", _fix_smart_quotes),
    ("fences", _strip_fences),
    ("python_literals", _fix_literals),
    ("trailing_comma", _fix_trailing_commas),
    ("extract_balanced", _extract_balanced),
)


def parse_json_loose(text):
    """Parse JSON from a raw LLM reply. Returns ``(value, repair_notes)``.

    ``repair_notes`` is an ordered list of the repair passes that fired
    (``fences``, ``trailing_comma``, ...). Raises ``ValueError`` when the
    text cannot be parsed even after repair — failure stays loud.
    """
    s = str(text)
    try:
        return json.loads(s), []
    except json.JSONDecodeError:
        pass
    notes: list = []
    for _round in range(2):
        for name, fn in PASSES:
            s2 = fn(s)
            if s2 != s and name not in notes:
                notes.append(name)
            s = s2
            try:
                return json.loads(s), notes
            except json.JSONDecodeError:
                continue
    raise ValueError(f"unparseable JSON: {str(text)[:60]!r}")


def validate_schema(obj, schema, path: str = "$") -> list:
    """Validate *obj* against a lite JSON-Schema subset; returns error list.

    Supported keywords: ``type``, ``required``, ``properties``, ``items``,
    ``enum``. An empty list means valid. Booleans never satisfy
    ``integer``/``number`` despite Python's ``bool < int`` subclassing.
    """
    errors: list = []
    schema = schema or {}
    t = schema.get("type")
    if t:
        want = TYPES.get(t)
        if want is None:
            errors.append(f"{path}: unknown type '{t}'")
            return errors
        if not isinstance(obj, want) or (type(obj) is bool and t in ("integer", "number")):
            errors.append(f"{path}: want {t}, got {type(obj).__name__}")
            return errors
    if "enum" in schema and obj not in schema["enum"]:
        errors.append(f"{path}: {obj!r} not in enum {schema['enum']!r}")
    if isinstance(obj, dict):
        for req in schema.get("required", []):
            if req not in obj:
                errors.append(f"{path}: missing required '{req}'")
        for key, sub in (schema.get("properties") or {}).items():
            if key in obj:
                errors.extend(validate_schema(obj[key], sub, f"{path}.{key}"))
    if isinstance(obj, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for i, v in enumerate(obj):
                errors.extend(validate_schema(v, items, f"{path}[{i}]"))
    return errors
