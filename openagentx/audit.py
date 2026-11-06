"""Secret scanner — the repo audits itself.

``run_audit(root)`` walks source-ish files and reports every high-confidence
credential-shaped string as a finding ``{file, line, kind, snippet}``. Snippets
are themselves redacted (a report must never reproduce the secret). Binary
files, oversized files, and VCS/metadata directories are skipped. On this
repository the result must always be **0 findings**: fixture credentials are
assembled at runtime by concatenation and therefore never appear in any file.
"""

from __future__ import annotations

import os

from .redact import PATTERNS, redact

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
             ".next", "dist", "build", ".pytest_cache"}
MAX_BYTES = 1_000_000
SUFFIXES = (".py", ".md", ".txt", ".json", ".toml", ".cfg", ".ini", ".yml", ".yaml",
            ".js", ".mjs", ".ts", ".html", ".css", ".sh")


def run_audit(root: str = ".") -> list:
    findings: list = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if not name.endswith(SUFFIXES):
                continue
            try:
                if os.path.getsize(path) > MAX_BYTES:
                    continue
                with open(path, encoding="utf-8") as fh:
                    lines = fh.readlines()
            except (OSError, UnicodeDecodeError):
                continue  # binary or unreadable: skipped, never crashed on
            for i, line in enumerate(lines, 1):
                for kind, pattern in PATTERNS:
                    m = pattern.search(line)
                    if m:
                        safe, _ = redact(line.strip())
                        findings.append({
                            "file": os.path.relpath(path, root),
                            "line": i,
                            "kind": kind,
                            "snippet": safe[:160],
                        })
    return findings
