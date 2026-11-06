"""X-Prompt: layered, budget-aware prompt compiler.

Prompts are **files, not code constants**. Sections live in layered
directories with clear precedence (low → high):

1. ``prompts/base`` — shipped defaults
2. pack layers (see :mod:`openagentx.packs`)
3. ``.openagentx/prompts`` — project overrides
4. ``~/.openagentx/prompts`` — personal overrides

Higher layers *replace* a section. To *wrap* the default instead of
replacing it (extend, don't fork — the cleanest extension mechanism found
in the reference analysis), an override may contain the token::

    {{include original}}

The compiler also enforces the X-Budget thesis at the prompt layer: if the
composed system prompt exceeds the token budget, the lowest-priority
sections are replaced with one-line stubs. ``protocol`` and ``output`` are
never dropped — a model without its action contract cannot work at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

INCLUDE_TOKEN = "{{include original}}"

# section id → markdown file name (in prompts/base); sections without a file
# (tools, memory) render from runtime context only.
SECTION_FILES: dict[str, str] = {
    "identity": "10-identity.md",
    "guardrails": "20-guardrails.md",
    "protocol": "30-protocol.md",
    "output": "40-output-contract.md",
}

_TITLES = {
    "identity": "Identity",
    "guardrails": "Guardrails",
    "protocol": "Action protocol",
    "tools": "Tools",
    "memory": "Recalled memory",
    "output": "Output contract",
}

# section id → (trim priority, stub line). Lower priority = trimmed first.
# priority 0 = never trimmed.
DEFAULT_SECTIONS: dict[str, tuple[int, str]] = {
    "protocol": (0, "Respond with one JSON object: {\"action\":{\"tool\":…,\"args\":…}} or {\"reply\":…}."),
    "output": (1, "Finish with result + evidence + limits; no evidence, no success claim."),
    "guardrails": (2, "Respect policy verdicts; stay in the workspace; never handle secrets."),
    "identity": (3, "You are an OpenAgent-X agent: small reversible steps, evidence before claims."),
    "tools": (4, ""),
    "memory": (5, ""),
}

_BASE_DIR = Path(__file__).resolve().parent.parent / "prompts" / "base"


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (≈4 chars/token) — good enough for budgeting."""
    return len(text) // 4 + 1


class PromptCompiler:
    """Compose a system prompt from layered section files under a budget."""

    def __init__(
        self,
        base_dir: Path | None = None,
        override_dirs: list[Path] | None = None,
        sections: dict[str, tuple[int, str]] | None = None,
    ) -> None:
        self.base_dir = Path(base_dir or _BASE_DIR)
        # precedence order: base first, then overrides in given order (last wins)
        self.layers: list[Path] = [self.base_dir] + list(override_dirs or [])
        self.sections = sections or DEFAULT_SECTIONS

    # ------------------------------------------------------------------ public

    def compile(
        self,
        *,
        tools_section: str = "",
        memory_block: str = "",
        token_budget: int | None = None,
    ) -> str:
        """Build the system prompt. ``token_budget=None`` means unlimited."""
        context = {
            "tools": tools_section,
            "memory": memory_block,
        }
        rendered: dict[str, str] = {}
        for section_id in self.sections:
            text = self._render_section(section_id, context)
            if text:
                rendered[section_id] = text

        if token_budget is not None:
            rendered = self._fit_budget(rendered, token_budget)

        parts = []
        for sid in ("identity", "guardrails", "protocol", "tools", "memory", "output"):
            if sid not in rendered:
                continue
            text = rendered[sid]
            if not text.lstrip().startswith("#"):
                text = f"# {_TITLES.get(sid, sid.title())}\n{text}"
            parts.append(text)
        return "\n\n".join(parts).strip()

    def layer_dirs(self) -> list[Path]:
        """Existing layer directories in precedence order (low → high)."""
        return [p for p in self.layers if p.exists()]

    # ----------------------------------------------------------------- private

    def _render_section(self, section_id: str, context: dict[str, str]) -> str:
        """Highest-precedence version of one section, honoring {{include original}}."""
        base = self._read(self.base_dir / self._filename(section_id))
        override = ""
        for layer in self.layers[1:]:
            candidate = self._read(layer / self._filename(section_id))
            if candidate:
                override = candidate  # last existing layer wins
        text = override if override else base
        if not text:
            return context.get(section_id, "")
        if INCLUDE_TOKEN in text and base:
            text = text.replace(INCLUDE_TOKEN, base.strip())

        return text.strip()

    def _fit_budget(self, rendered: dict[str, str], token_budget: int) -> dict[str, str]:
        """Trim lowest-priority sections to one-line stubs until under budget."""
        total = sum(estimate_tokens(t) for t in rendered.values())
        if total <= token_budget:
            return rendered
        trimmed = dict(rendered)
        by_priority = sorted(
            (sid for sid in trimmed),
            key=lambda sid: -self.sections.get(sid, (9, ""))[0],  # highest number first
        )
        for sid in by_priority:
            priority, stub = self.sections.get(sid, (9, ""))
            if priority == 0:
                continue  # protocol is never dropped
            trimmed[sid] = stub
            total = sum(estimate_tokens(t) for t in trimmed.values())
            if total <= token_budget:
                break
        return trimmed

    @staticmethod
    def _filename(section_id: str) -> str:
        return SECTION_FILES.get(section_id, f"{section_id}.md")

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""


def project_override_dirs() -> list[Path]:
    """Standard override layers for the current workspace."""
    dirs = [Path(".openagentx/prompts")]
    home = os.environ.get("OPENAGENTX_HOME") or os.path.expanduser("~/.openagentx")
    dirs.append(Path(home) / "prompts")
    return dirs
