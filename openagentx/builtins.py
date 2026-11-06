"""Built-in tools: stdlib-only capabilities with declared permission tiers.

Safety properties baked into the handlers themselves:

* **Workspace confinement** — filesystem tools resolve paths against the
  workspace root (``OPENAGENTX_WORKSPACE`` or CWD) and refuse to escape it.
  Denial parity: no handler offers a bypass path around the policy engine.
* **Diffs-not-dumps** — ``fs_write`` returns a unified diff of what changed,
  not the whole file.
* **Bounded execution** — ``shell`` / ``python_exec`` run with hard timeouts
  and output caps; ``web_fetch`` allows only http(s), with size caps.
* **Honest tiers** — every tool declares its tier; the policy engine, not
  this file, decides what runs.
"""

from __future__ import annotations

import difflib
import html
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from openagentx.policy import Tier
from openagentx.tools import Tool, ToolRegistry, ToolResult

MAX_READ_CHARS = 8_000
MAX_FETCH_CHARS = 6_000
EXEC_TIMEOUT_SECONDS = 20


def workspace_root() -> Path:
    """The directory filesystem tools are confined to."""
    return Path(os.environ.get("OPENAGENTX_WORKSPACE", os.getcwd())).resolve()


def _resolve(path: str) -> Path:
    root = workspace_root()
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if not (resolved == root or root in resolved.parents):
        raise ValueError(f"path escapes workspace root {root}: {path}")
    return resolved


# --------------------------------------------------------------------- tools


def fs_read(path: str) -> ToolResult:
    """Read a UTF-8 text file (head-capped)."""
    target = _resolve(path)
    if not target.exists() or not target.is_file():
        return ToolResult(ok=False, output=f"not a file: {path}")
    text = target.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n… [truncated; {target.stat().st_size} bytes total]"
    return ToolResult(ok=True, output=text)


def fs_list(path: str = ".") -> ToolResult:
    """List a workspace directory (name, type, size)."""
    target = _resolve(path)
    if not target.exists():
        return ToolResult(ok=False, output=f"no such path: {path}")
    entries = []
    for child in sorted(target.iterdir())[:200]:
        kind = "dir" if child.is_dir() else "file"
        size = "" if child.is_dir() else f" {child.stat().st_size}B"
        entries.append(f"{child.name}{'/' if child.is_dir() else ''} {kind}{size}")
    return ToolResult(ok=True, output="\n".join(entries) or "(empty)")


def fs_write(path: str, content: str) -> ToolResult:
    """Write a UTF-8 text file and return a unified diff of the change."""
    target = _resolve(path)
    before = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    diff = "\n".join(
        list(difflib.unified_diff(
            before.splitlines(), content.splitlines(),
            fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="",
        ))[:40]
    )
    return ToolResult(ok=True, output=f"wrote {path} ({len(content)} chars)", diff=diff)


def shell(cmd: str) -> ToolResult:
    """Run one shell command in the workspace (sandbox advised; P2 tier)."""
    proc = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        timeout=EXEC_TIMEOUT_SECONDS, cwd=str(workspace_root()),
    )
    out = (proc.stdout or "") + (("\n[stderr] " + proc.stderr) if proc.stderr else "")
    out = out.strip() or "(no output)"
    return ToolResult(
        ok=proc.returncode == 0,
        output=out[:MAX_READ_CHARS] + (f"\n[exit={proc.returncode}]" if proc.returncode else ""),
        meta={"exit_code": proc.returncode},
    )


def python_exec(code: str) -> ToolResult:
    """Run a short Python snippet in a subprocess (P2 tier)."""
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code],  # -I: isolated mode, no user site
        capture_output=True, text=True, timeout=EXEC_TIMEOUT_SECONDS,
        cwd=str(workspace_root()),
    )
    out = (proc.stdout or "") + (("\n[stderr] " + proc.stderr) if proc.stderr else "")
    return ToolResult(ok=proc.returncode == 0, output=(out.strip() or "(no output)")[:MAX_READ_CHARS])


_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")


def web_fetch(url: str) -> ToolResult:
    """Fetch an http(s) URL and return readable text (P3 tier)."""
    if not url.lower().startswith(("http://", "https://")):
        return ToolResult(ok=False, output="only http/https URLs are allowed")
    request = urllib.request.Request(
        url, headers={"User-Agent": "OpenAgent-X/0.1 (+web_fetch; bounded)"}
    )
    with urllib.request.urlopen(request, timeout=EXEC_TIMEOUT_SECONDS) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read(MAX_FETCH_CHARS * 4).decode(charset, errors="replace")
    text = _ANY_TAG.sub(" ", _TAG.sub(" ", raw))
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return ToolResult(ok=True, output=text[:MAX_FETCH_CHARS])


def think(note: str) -> ToolResult:
    """Private scratchpad: plan without side effects (never shown to users)."""
    return ToolResult(ok=True, output=f"noted ({len(note)} chars) — continue with an action or reply")


def find_tools_impl(registry: ToolRegistry) -> Any:
    """Build the ``find_tools`` handler bound to a registry (JIT disclosure)."""

    def handler(query: str) -> ToolResult:
        tools = registry.find_tools(query)
        if not tools:
            return ToolResult(ok=True, output=f"no tools match {query!r}")
        return ToolResult(ok=True, output="\n".join(f"- {t.signature()}" for t in tools))

    return handler


# ------------------------------------------------------------------- wiring


def register_builtins(registry: ToolRegistry, *, include_exec: bool = True,
                      include_network: bool = True) -> None:
    """Register the standard toolset on a registry.

    Callers choose which risky groups to include; the policy engine still
    gates every dispatch. ``find_tools`` is always registered so JIT
    discovery works.
    """
    registry.register(Tool(
        name="fs_read", tier=Tier.P0, core=True,
        description="read a text file inside the workspace",
        params={"path": "str — workspace-relative path"},
        handler=fs_read,
    ))
    registry.register(Tool(
        name="fs_list", tier=Tier.P0, core=True,
        description="list a directory inside the workspace",
        params={"path": "str — workspace-relative path (default '.')"},
        handler=fs_list,
    ))
    registry.register(Tool(
        name="think", tier=Tier.P0, core=True,
        description="private scratchpad to plan or reason without side effects",
        params={"note": "str — private note to yourself"},
        handler=think,
    ))
    registry.register(Tool(
        name="fs_write", tier=Tier.P1, core=True, returns_diff=True,
        description="create or overwrite a text file; returns the unified diff",
        params={"path": "str — workspace-relative path", "content": "str — full file content"},
        handler=fs_write,
    ))
    if include_exec:
        registry.register(Tool(
            name="shell", tier=Tier.P2,
            description="run one shell command in the workspace (timeout-bounded)",
            params={"cmd": "str — shell command"},
            handler=shell,
        ))
        registry.register(Tool(
            name="python_exec", tier=Tier.P2,
            description="run a short Python snippet in an isolated subprocess",
            params={"code": "str — python source"},
            handler=python_exec,
        ))
    if include_network:
        registry.register(Tool(
            name="web_fetch", tier=Tier.P3,
            description="fetch one http(s) page and return readable text",
            params={"url": "str — absolute http(s) URL"},
            handler=web_fetch,
        ))
    registry.register(Tool(
        name="find_tools", tier=Tier.P0, core=True,
        description="discover more tools by keyword (JIT tool disclosure)",
        params={"query": "str — keywords like 'search web' or 'run code'"},
        handler=find_tools_impl(registry),
    ))
