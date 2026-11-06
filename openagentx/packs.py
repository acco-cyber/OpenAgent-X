"""X-Packs: keyword-triggered domain knowledge packs.

A pack is a directory of distilled expert knowledge that activates when its
trigger words appear in a task — the generalized form of the "microagent"
pattern found in the reference analysis, made *portable and declared*:

```
packs/<name>/
├── pack.json     # name, version, description, triggers[], permissions[]
├── PACK.md       # the understanding payload (checklists, pitfalls, patterns)
└── prompts/      # optional prompt-section overrides (layered, {{include original}}-aware)
```

Two contract properties make packs safe:

* **Declared permissions** — a pack states which permission tiers its
  guidance may require (e.g. web research → P3). The policy engine remains
  the only authority; the declaration is advisory metadata for humans and
  audits, surfaced by ``PackLoader.describe_activation``.
* **Nothing activates silently** — activations are returned as data (and
  traced as ``pack.activated`` by the caller), never injected invisibly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PACK_MANIFEST = "pack.json"
PACK_BODY = "PACK.md"

DEFAULT_PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"


@dataclass(frozen=True)
class Pack:
    """One installed knowledge pack."""

    name: str
    version: str
    description: str
    triggers: tuple[str, ...]
    permissions: tuple[str, ...]          # advisory; policy engine still decides
    root: Path
    body: str = ""
    prompts_dir: Path | None = None

    @property
    def prompt_layers(self) -> list[Path]:
        """Prompt override layers this pack contributes (may be empty)."""
        return [self.prompts_dir] if (self.prompts_dir and self.prompts_dir.exists()) else []

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "triggers": list(self.triggers),
            "permissions": list(self.permissions),
            "root": str(self.root),
        }


@dataclass
class Activation:
    """The result of matching packs against a task — explicit, auditable."""

    packs: list[Pack] = field(default_factory=list)

    def knowledge_block(self, max_chars: int = 6_000) -> str:
        """Prompt-ready knowledge sections from all activated packs."""
        blocks = []
        for pack in self.packs:
            if pack.body:
                blocks.append(f"## Knowledge pack: {pack.name} (v{pack.version})\n\n{pack.body}")
        text = "\n\n".join(blocks)
        return text[:max_chars] + ("\n… [pack knowledge truncated]" if len(text) > max_chars else "")

    def override_dirs(self) -> list[Path]:
        """Prompt layers contributed by activated packs (precedence order)."""
        dirs: list[Path] = []
        for pack in self.packs:
            dirs.extend(pack.prompt_layers)
        return dirs

    def describe_activation(self) -> str:
        """Human/audit summary: which packs and which declared permissions."""
        if not self.packs:
            return "no packs activated"
        return "; ".join(
            f"{p.name} v{p.version} (triggers hit; declares tiers {','.join(p.permissions) or 'none'})"
            for p in self.packs
        )


class PackLoader:
    """Discovers, validates, and matches packs from one or more directories."""

    def __init__(self, *dirs: Path | str) -> None:
        self.dirs = [Path(d) for d in dirs] or [DEFAULT_PACKS_DIR]

    # ------------------------------------------------------------------ loading

    def catalog(self) -> list[Pack]:
        """All valid packs found across loader directories."""
        packs: list[Pack] = []
        seen: set[str] = set()
        for base in self.dirs:
            if not base.exists():
                continue
            for child in sorted(base.iterdir()):
                if not (child / PACK_MANIFEST).is_file():
                    continue
                try:
                    pack = self._load_one(child)
                except (ValueError, json.JSONDecodeError, OSError):
                    continue  # an invalid pack never breaks the catalog
                if pack.name not in seen:
                    seen.add(pack.name)
                    packs.append(pack)
        return packs

    def get(self, name: str) -> Pack | None:
        return next((p for p in self.catalog() if p.name == name), None)

    def match(self, task_text: str) -> Activation:
        """Return packs whose trigger words appear in the task text."""
        hay = task_text.lower()
        activated = [
            pack for pack in self.catalog()
            if any(trigger.lower() in hay for trigger in pack.triggers)
        ]
        return Activation(packs=activated)

    # ----------------------------------------------------------------- private

    def _load_one(self, root: Path) -> Pack:
        data = json.loads((root / PACK_MANIFEST).read_text(encoding="utf-8"))
        for required in ("name", "version", "description", "triggers"):
            if not data.get(required):
                raise ValueError(f"{root}: pack manifest missing {required!r}")
        if not isinstance(data["triggers"], list) or not data["triggers"]:
            raise ValueError(f"{root}: 'triggers' must be a non-empty list")
        body_path = root / data.get("knowledge", PACK_BODY)
        prompts_dir = root / "prompts"
        return Pack(
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data["description"]),
            triggers=tuple(str(t) for t in data["triggers"]),
            permissions=tuple(str(p) for p in data.get("permissions", [])),
            root=root,
            body=body_path.read_text(encoding="utf-8") if body_path.is_file() else "",
            prompts_dir=prompts_dir if prompts_dir.is_dir() else None,
        )
