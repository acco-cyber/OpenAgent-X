"""LLM adapters — offline-first, deterministic.

The graded path never touches the network: :class:`ScriptedLLM` replays a
single-line-JSON script where each line is either::

    {"action": {"tool": "calc", "args": {"expr": "2+2"}}, "thought": "why"}
    {"reply": "the final answer"}

Any exhaustion or malformed line raises immediately — drills must observe real
failures, not improvised behavior.
"""

from __future__ import annotations

import json


class ScriptExhausted(RuntimeError):
    """The script ran out of lines while the loop still needed a turn."""


class ScriptParseError(RuntimeError):
    """A script line was not a valid single-line JSON turn."""


class LLMUnavailable(RuntimeError):
    """Base for adapter availability failures (multi-model routing).

    Routers raise subclasses of this when adapters refuse a turn; runners and
    team loops catch it to journal an explicit, honest stop — never a crash.
    """


class ScriptedLLM:
    """Deterministic offline LLM: returns scripted turns in order."""

    def __init__(self, script, name: str = "scripted"):
        self.script = list(script)
        self.name = name
        self.cursor = 0
        self.calls = 0

    def complete(self, messages) -> dict:
        """Return the next scripted turn: ``{"reply": str}`` or
        ``{"action": {...}, "thought": str}``."""
        self.calls += 1
        if self.cursor >= len(self.script):
            raise ScriptExhausted(
                f"script exhausted: call {self.calls} beyond {len(self.script)} lines"
            )
        line = self.script[self.cursor]
        self.cursor += 1
        try:
            obj = json.loads(line) if isinstance(line, str) else dict(line)
        except (json.JSONDecodeError, TypeError) as e:
            raise ScriptParseError(f"script line {self.cursor} is not valid JSON: {e}") from e
        if "reply" in obj:
            return {"reply": str(obj["reply"])}
        if "action" in obj:
            act = obj["action"]
            if not isinstance(act, dict) or "tool" not in act:
                raise ScriptParseError(f"script line {self.cursor}: action needs a tool")
            return {
                "action": {"tool": str(act["tool"]), "args": dict(act.get("args", {}))},
                "thought": str(obj.get("thought", "")),
            }
        raise ScriptParseError(f"script line {self.cursor}: needs reply or action")


class EchoLLM:
    """Trivial adapter that echoes the last user message (smoke tests only)."""

    def __init__(self):
        self.calls = 0

    def complete(self, messages) -> dict:
        self.calls += 1
        last = ""
        for m in messages:
            if m.get("role") == "user":
                last = str(m.get("content", ""))
        return {"reply": f"echo: {last}"}
