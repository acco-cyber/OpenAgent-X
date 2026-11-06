"""X-Memory: 3-tier, file-backed memory that never lies and never leaks.

Aligned with ``schemas/memory-record.schema.json``. Design fused from the
reference analysis:

* **Three tiers** — ``working`` (this session), ``context`` (this project),
  ``long`` (the human's durable preferences). Each tier is one JSONL file
  under ``.openagentx/memory/`` — grep-able, diffable, portable.
* **Status lifecycle** — records are born ``candidate``; promotion to
  ``verified`` is an explicit, evidence-gated act; ``superseded`` records are
  kept for history but never recalled as truth.
* **Supersede, don't duplicate** — new evidence creates a *new* record and
  marks the old one superseded (with provenance), so memory converges on
  truth instead of accumulating contradictions.
* **Human-editable export** — :meth:`MemoryStore.export_markdown` renders a
  plain ``MEMORY.md`` the human can edit by hand; files over databases.
* **Daily rollups** — one idempotent ``procedure`` record per day compresses
  the day's activity (tagged ``rollup:YYYY-MM-DD``).
* Secrets and sensitive personal data must NEVER be stored; the store runs
  the same redaction used at the trace boundary before persisting.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from openagentx.events import redact, utc_now_iso

DOMAINS = ("project", "user", "knowledge", "execution", "task")
TYPES = ("decision", "fact", "preference", "procedure", "artifact_summary")
STATUSES = ("candidate", "verified", "superseded", "rejected")
VISIBILITIES = ("private", "project", "team")
TIERS = ("working", "context", "long")

_STATUS_WEIGHT = {"verified": 1.0, "candidate": 0.6}
DEFAULT_MEMORY_DIR = ".openagentx/memory"


@dataclass
class MemoryRecord:
    """One knowledge record. Field names mirror the universal schema."""

    content: str
    domain: str = "task"                  # project | user | knowledge | execution | task
    type: str = "fact"                    # decision | fact | preference | procedure | artifact_summary
    project_id: str | None = None
    source_refs: list[str] = field(default_factory=list)
    confidence: float = 0.6
    status: str = "candidate"             # candidate | verified | superseded | rejected
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now_iso)
    expires_at: str | None = None
    visibility: str = "project"           # private | project | team
    supersedes: str | None = None         # provenance chain
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "project_id": self.project_id,
            "domain": self.domain,
            "type": self.type,
            "content": self.content,
            "source_refs": self.source_refs,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "visibility": self.visibility,
            "supersedes": self.supersedes,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        known = {f for f in cls.__dataclass_fields__}  # noqa: C416 - clarity
        return cls(**{k: v for k, v in data.items() if k in known})


class MemoryStore:
    """Three JSONL-backed tiers with recall scoring and lifecycle control."""

    def __init__(self, root: str | Path | None = None, project_id: str | None = None) -> None:
        self.root = Path(root or DEFAULT_MEMORY_DIR)
        self.project_id = project_id
        self.root.mkdir(parents=True, exist_ok=True)
        self._working: list[MemoryRecord] = []

    # ------------------------------------------------------------------ paths

    def _file(self, tier: str) -> Path:
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier!r}; use one of {TIERS}")
        return self.root / f"{tier}.jsonl"

    # ------------------------------------------------------------------- write

    def remember(
        self,
        content: str,
        *,
        tier: str = "context",
        domain: str = "task",
        type: str = "fact",  # noqa: A002 - mirrors schema field name
        confidence: float = 0.6,
        source_refs: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        """Store a new **candidate** record (secrets redacted before persist)."""
        record = MemoryRecord(
            content=redact(content.strip()),
            domain=domain if domain in DOMAINS else "task",
            type=type if type in TYPES else "fact",
            project_id=self.project_id,
            confidence=max(0.0, min(1.0, confidence)),
            source_refs=source_refs or [],
            tags=tags or [],
        )
        if tier == "working":
            self._working.append(record)
        else:
            self._append(self._file(tier), record)
        return record

    def promote(self, memory_id: str) -> bool:
        """candidate → verified. Call only with evidence (schema contract)."""
        return self._set_status(memory_id, "verified")

    def reject(self, memory_id: str) -> bool:
        return self._set_status(memory_id, "rejected")

    def supersede(self, memory_id: str, new_content: str, **kwargs: Any) -> MemoryRecord | None:
        """Replace one record's knowledge with newer truth, keeping history."""
        old, tier = self._locate(memory_id)
        if old is None:
            return None
        self._set_status(memory_id, "superseded")
        kwargs.setdefault("domain", old.domain)
        kwargs.setdefault("type", old.type)
        kwargs.setdefault("source_refs", list(old.source_refs) + [f"memory:{old.memory_id}"])
        replacement = self.remember(new_content, **kwargs)
        replacement.supersedes = old.memory_id
        return replacement

    def daily_rollup(self, day: date | None = None) -> MemoryRecord | None:
        """One idempotent ``procedure`` record summarizing a day's records."""
        stamp = f"rollup:{(day or date.today()).isoformat()}"
        existing = [
            r for r in self._load(self._file("context"))
            if stamp in r.tags
        ]
        if existing:
            return existing[0]
        target_day = (day or date.today()).isoformat()
        records = [
            r for r in self._load(self._file("context"))
            if r.created_at.startswith(target_day) and r.status in ("candidate", "verified")
        ]
        if not records:
            return None
        lines = [f"- [{r.type}] {r.content}" for r in records[:50]]
        return self.remember(
            f"Daily rollup {target_day}:\n" + "\n".join(lines),
            tier="context", domain="project", type="procedure",
            tags=[stamp], confidence=0.9,
        )

    # ------------------------------------------------------------------- read

    def recall(
        self,
        query: str,
        *,
        tiers: tuple[str, ...] = TIERS,
        limit: int = 8,
        include_superseded: bool = False,
    ) -> list[MemoryRecord]:
        """Scored recall: term overlap × status weight × recency bonus."""
        terms = [t for t in query.lower().split() if len(t) > 1]
        pool: list[MemoryRecord] = []
        for tier in tiers:
            if tier == "working":
                pool.extend(self._working)
            else:
                pool.extend(self._load(self._file(tier)))
        now = utc_now_iso()
        scored: list[tuple[float, MemoryRecord]] = []
        for record in pool:
            if not include_superseded and record.status in ("superseded", "rejected"):
                continue
            hay = record.content.lower()
            overlap = sum(1 for t in terms if t in hay)
            if not terms or overlap == 0:
                continue
            score = overlap * _STATUS_WEIGHT.get(record.status, 0.3)
            try:  # recency bonus: newer records win ties
                age_days = max(
                    0.0,
                    (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(record.created_at)
                    ).total_seconds() / 86400,
                )
            except ValueError:
                age_days = 30.0
            score *= 1.0 + max(0.0, 1.0 - age_days / 30.0) * 0.25
            score *= 0.5 + record.confidence
            scored.append((score, record))
        scored.sort(key=lambda pair: (-pair[0], pair[1].created_at), reverse=False)
        scored.sort(key=lambda pair: -pair[0])
        return [r for _s, r in scored[:limit]]

    def context_block(self, query: str, token_budget: int = 512) -> str:
        """Prompt-ready memory text under a hard token budget (≈4 chars/token)."""
        records = self.recall(query)
        lines: list[str] = []
        used = 0
        for record in records:
            line = f"- ({record.status}/{record.type}) {record.content}"
            cost = len(line) // 4 + 1
            if used + cost > token_budget:
                break
            lines.append(line)
            used += cost
        return "\n".join(lines) if lines else "(no relevant memory)"

    def export_markdown(self, path: str | Path | None = None) -> Path:
        """Render every tier to one human-editable ``MEMORY.md``."""
        target = Path(path or self.root / "MEMORY.md")
        sections: list[str] = ["# OpenAgent-X Memory", "", "> Edit freely — this file is yours.", ""]
        for tier in TIERS:
            records = list(self._working) if tier == "working" else self._load(self._file(tier))
            sections += [f"## {tier} ({len(records)})", ""]
            for record in records:
                marker = {"verified": "✓", "candidate": "?", "superseded": "↻", "rejected": "✗"}[record.status]
                sections.append(f"- [{marker}] `{record.type}` {record.content}")
            sections.append("")
        target.write_text("\n".join(sections), encoding="utf-8")
        return target

    # --------------------------------------------------------------- internals

    def _append(self, path: Path, record: MemoryRecord) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def _load(self, path: Path) -> list[MemoryRecord]:
        if not path.exists():
            return []
        records: list[MemoryRecord] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(MemoryRecord.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return records

    def _locate(self, memory_id: str) -> tuple[MemoryRecord | None, str]:
        if any(r.memory_id == memory_id for r in self._working):
            return next(r for r in self._working if r.memory_id == memory_id), "working"
        for tier in ("context", "long"):
            for r in self._load(self._file(tier)):
                if r.memory_id == memory_id:
                    return r, tier
        return None, ""

    def _set_status(self, memory_id: str, status: str) -> bool:
        record, tier = self._locate(memory_id)
        if record is None:
            return False
        record.status = status
        if tier == "working":
            return True
        path = self._file(tier)
        rewritten = []
        for r in self._load(path):
            if r.memory_id == memory_id:
                r.status = status
            rewritten.append(r.to_dict())
        with path.open("w", encoding="utf-8") as fh:
            for data in rewritten:
                fh.write(json.dumps(data, ensure_ascii=False) + "\n")
        return True
