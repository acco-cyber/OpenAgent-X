"""Tool registry and sandboxed builtin tools.

Contracts:
- Every tool returns a JSON-able ``dict`` — no free-form side channels.
- Args are validated against a minimal JSON-schema subset (required + known keys).
- Filesystem tools are sandboxed: resolved paths must stay inside ``workdir``.
- ``vault_read`` exists solely to exercise redaction with a runtime-concatenated
  fixture token (never a real credential, and invisible to ``oax audit .``).
"""

from __future__ import annotations

import ast
import json
import os
import time
from dataclasses import dataclass
from typing import Callable


class ToolError(Exception):
    """Raised for contract violations (unknown tool, bad args, sandbox escape)."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[..., dict]


def _check_args(schema: dict, args: dict) -> None:
    props = schema.get("properties", {})
    for k in schema.get("required", []):
        if k not in args:
            raise ToolError(f"missing required arg '{k}'")
    for k in args:
        if k not in props:
            raise ToolError(f"unknown arg '{k}'")


class ToolRegistry:
    """Name→tool map with duplicate protection and result envelopes."""

    def __init__(self):
        self._tools: dict = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError(f"duplicate tool '{tool.name}'")
        self._tools[tool.name] = tool

    def names(self) -> list:
        return sorted(self._tools)

    def get(self, name: str):
        return self._tools.get(name)

    def call(self, name: str, args: dict) -> dict:
        """Call a tool, returning ``{"ok": True, "result": ...}`` or
        ``{"ok": False, "error": ...}`` — never raises across the boundary."""
        t = self.get(name)
        if t is None:
            return {"ok": False, "error": f"unknown tool '{name}'"}
        try:
            _check_args(t.schema, args)
            out = t.fn(**args)
            if not isinstance(out, dict):
                raise ToolError("tool must return a dict")
            return {"ok": True, "result": out}
        except ToolError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # contract: tools never crash the loop
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _resolve_in(workdir: str, path: str) -> str:
    base = os.path.realpath(workdir)
    p = os.path.realpath(os.path.join(base, str(path)))
    if p != base and not p.startswith(base + os.sep):
        raise ToolError(f"path escapes workdir: {path}")
    return p


def _safe_calc(expr: str):
    """Arithmetic-only AST evaluator (+ - * / // % ** parens, unary minus)."""
    node = ast.parse(str(expr), mode="eval")

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(
            n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
        ):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
            if isinstance(n.op, ast.FloorDiv):
                return a // b
            if isinstance(n.op, ast.Mod):
                return a % b
            return a ** b
        raise ToolError(f"expression rejected: {expr!r}")

    return ev(node.body)


def vault_value(key: str) -> str:
    """Runtime-concatenated fixture credentials (audit-invisible by construction)."""
    if key == "github":
        return "ghp_" + "A1b2C3d4E5" * 3 + "F9ab12"
    if key == "aws":
        # canonical AWS access-key shape: exactly 20 chars (AKIA + 16) so the
        # high-confidence pattern consumes the whole value — no residue leaks
        return "AKIA" + "IO3XT7Q9RL2M" + "4Y8K"
    raise ToolError(f"unknown vault key '{key}'")


def builtin_tools(workdir: str = ".") -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(Tool(
        "think", "record a reasoning note (no side effects)",
        {"properties": {"note": {"type": "string"}}, "required": ["note"]},
        lambda note: {"note": str(note)},
    ))
    reg.register(Tool(
        "echo", "echo text back (tests plumbing)",
        {"properties": {"text": {"type": "string"}}, "required": ["text"]},
        lambda text: {"text": str(text)},
    ))
    reg.register(Tool(
        "calc", "evaluate an arithmetic expression",
        {"properties": {"expr": {"type": "string"}}, "required": ["expr"]},
        lambda expr: {"expr": str(expr), "value": _safe_calc(expr)},
    ))
    reg.register(Tool(
        "now", "current UTC time (never graded — observability only)",
        {"properties": {}, "required": []},
        lambda: {"iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    ))
    reg.register(Tool(
        "write_file", "write text inside workdir",
        {"properties": {"path": {"type": "string"}, "text": {"type": "string"}},
         "required": ["path", "text"]},
        lambda path, text: _write_file(workdir, path, text),
    ))
    reg.register(Tool(
        "read_file", "read a file inside workdir",
        {"properties": {"path": {"type": "string"}}, "required": ["path"]},
        lambda path: _read_file(workdir, path),
    ))
    reg.register(Tool(
        "list_dir", "list a directory inside workdir",
        {"properties": {"path": {"type": "string", "default": "."}}, "required": []},
        lambda path=".": _list_dir(workdir, path),
    ))
    reg.register(Tool(
        "vault_read", "read a fixture credential from the fake vault (redaction drill)",
        {"properties": {"key": {"type": "string"}}, "required": ["key"]},
        lambda key: {"key": str(key), "value": vault_value(str(key))},
    ))
    reg.register(Tool(
        "vault_bundle", "nested fixture credential bundle (deep-redaction drill)",
        {"properties": {}, "required": []},
        lambda: {
            "profile": {"name": "ci-bot", "org": "fixture"},
            "creds": [
                {"kind": "github", "token": vault_value("github")},
                {"kind": "aws", "token": vault_value("aws")},
            ],
        },
    ))
    return reg


def _write_file(workdir: str, path: str, text: str) -> dict:
    p = _resolve_in(workdir, path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    data = str(text).encode("utf-8")
    with open(p, "wb") as fh:
        fh.write(data)
    return {"path": str(path), "bytes": len(data)}


def _read_file(workdir: str, path: str) -> dict:
    p = _resolve_in(workdir, path)
    with open(p, encoding="utf-8") as fh:
        return {"path": str(path), "text": fh.read()}


def _list_dir(workdir: str, path: str = ".") -> dict:
    p = _resolve_in(workdir, path)
    return {"path": str(path), "entries": sorted(os.listdir(p))}


def jsonable(obj) -> str:
    """Compact deterministic JSON for journal payloads."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)
