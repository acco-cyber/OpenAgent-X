"""Prompt layers: ordered includes, loud cycle detection, safe substitution.

Layered prompt assembly for agents — a set of named template layers, one
entry layer, and a deterministic two-phase render:

1. **Include resolution** (depth-first, declared order). ``[[include name]]``
   directives expand recursively, strictly left-to-right, so the final text
   preserves the author's layering order exactly. Includes may nest and
   share (diamond includes expand once per path — deterministic).
2. **Variable substitution.** ``{{name}}`` placeholders are replaced from a
   vars dict *after* include expansion, in one pass over the final text.

Honest failure contracts (all raise ``ValueError``, never silent):

- an unknown entry layer or unknown include names itself;
- an include cycle (``a -> b -> a``, or a layer including itself) is
  reported with the full path — cycles can never loop forever;
- an unresolved ``{{variable}}`` names every missing variable instead of
  rendering an empty string;
- a chain deeper than ``max_depth`` is rejected even though it is acyclic.

Injection safety by construction: because substitution happens *after*
include expansion and values are never re-scanned for directives, a
variable value containing ``[[include ...]]`` stays literal text — data can
never add structure to the prompt.
"""

from __future__ import annotations

import re

INCLUDE_RE = re.compile(r"\[\[include\s+([A-Za-z0-9_-]+)\s*\]\]")
VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class PromptLayers:
    """Resolve layered prompt templates with loud, deterministic errors."""

    def __init__(self, layers: dict, max_depth: int = 16):
        if not layers:
            raise ValueError("prompt layers need at least one layer")
        if int(max_depth) < 1:
            raise ValueError("max_depth must be >= 1")
        self.layers = {str(k): str(v) for k, v in layers.items()}
        self.max_depth = int(max_depth)

    def resolve(self, entry: str, _stack: tuple = (), _depth: int = 0) -> str:
        """Expand every ``[[include name]]`` under *entry* (order kept)."""
        entry = str(entry)
        if entry not in self.layers:
            known = ", ".join(sorted(self.layers))
            raise ValueError(
                f"unknown layer '{entry}' (known: {known})")
        if entry in _stack:
            path = " -> ".join(_stack + (entry,))
            raise ValueError(f"include cycle detected: {path}")
        if _depth > self.max_depth:
            raise ValueError(
                f"max include depth {self.max_depth} exceeded at '{entry}'")

        def _expand(match: "re.Match") -> str:
            return self.resolve(match.group(1), _stack + (entry,),
                                _depth + 1)

        return INCLUDE_RE.sub(_expand, self.layers[entry])

    def render(self, entry: str, vars: dict = None) -> str:
        """Resolve includes, then substitute ``{{name}}`` variables."""
        text = self.resolve(entry)
        values = {str(k): str(v) for k, v in (vars or {}).items()}
        used = {m.group(1) for m in VAR_RE.finditer(text)}
        missing = sorted(used - values.keys())
        if missing:
            raise ValueError(
                f"unresolved variables in prompt: {', '.join(missing)}")
        # one pass, values are literal text: never re-scanned for directives
        return VAR_RE.sub(lambda m: values[m.group(1)], text)
