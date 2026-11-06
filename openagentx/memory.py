"""Memory-lite: deterministic TF-IDF recall over past run journals.

The journal is the only truth — memory is a strictly *derived, read-only*
view. Indexing harvests the redacted text a journal already contains (the
task line, thoughts, replies) and never writes anywhere. Recall scores every
indexed run with smoothed TF-IDF and returns a deterministically ordered
ranking: score descending, then run id, then index order. No cache walls, no
hidden state — every recall recomputes from the term-document matrix built
out of the journals themselves.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter

_WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    ("a an and are as at be but by for from has have i in is it its of on or "
     "that the this to was were will with you your do does done then than "
     "them we our out up down over under again once just so no not now here "
     "there when why how what which while").split()
)


def tokenize(text: str) -> list:
    """Lowercase word tokens; stopwords and single characters are dropped."""
    return [w for w in _WORD_RE.findall(str(text).lower())
            if len(w) > 1 and w not in STOPWORDS]


def harvest_texts(events: list) -> list:
    """The only text memory may see: what the redacted journal already says."""
    out: list = []
    for ev in events:
        p = ev.payload or {}
        if ev.type == "run_start" and p.get("task"):
            out.append(str(p["task"]))
        elif ev.type == "thought" and p.get("text"):
            out.append(str(p["text"]))
        elif ev.type == "reply" and p.get("text"):
            out.append(str(p["text"]))
    return out


def _best_text(texts: list, terms: list) -> str:
    """Earliest harvested text mentioning any query term (deterministic)."""
    for t in texts:
        low = t.lower()
        if any(term in low for term in terms):
            return t
    return texts[0] if texts else ""


class MemoryLite:
    """TF-IDF index over past-run journals; read-only, offline, honest."""

    def __init__(self):
        self._docs: list = []

    @property
    def runs(self) -> int:
        return len(self._docs)

    def index_journal(self, path) -> dict:
        """Index one journal (strict read). Re-indexing a path is idempotent."""
        from .events import read_events

        events = read_events(path)
        if not events:
            raise ValueError(f"nothing to index: {path} has no events")
        texts = harvest_texts(events)
        tokens: list = []
        for t in texts:
            tokens.extend(tokenize(t))
        run_ids = sorted({e.run_id for e in events})
        doc = {
            "run_id": ",".join(run_ids),
            "journal": str(path),
            "terms": Counter(tokens),
            "length": len(tokens),
            "texts": texts,
        }
        self._docs = [d for d in self._docs if d["journal"] != doc["journal"]]
        self._docs.append(doc)
        return {"run_id": doc["run_id"], "journal": doc["journal"],
                "events": len(events), "terms": len(doc["terms"]),
                "tokens": doc["length"]}

    def index_dir(self, directory) -> int:
        """Index every ``*.jsonl`` journal in a directory (sorted). Returns count."""
        n = 0
        for name in sorted(os.listdir(str(directory))):
            if name.endswith(".jsonl"):
                self.index_journal(os.path.join(str(directory), name))
                n += 1
        return n

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = sum(1 for d in self._docs if term in d["terms"])
        return math.log((1 + n) / (1 + df)) + 1.0

    def recall(self, query: str, k: int = 3) -> list:
        """Ranked runs for ``query``: [{run_id, score, journal, snippet}]."""
        terms = tokenize(query)
        k = int(k)
        if not terms or k <= 0 or not self._docs:
            return []
        scored = []
        for idx, d in enumerate(self._docs):
            score = 0.0
            for term in dict.fromkeys(terms):
                tf = d["terms"].get(term, 0) / d["length"] if d["length"] else 0.0
                if tf:
                    score += tf * self._idf(term)
            if score > 0.0:
                scored.append((-score, d["run_id"], idx))
        scored.sort()
        hits = []
        for _neg, run_id, idx in scored[:k]:
            d = self._docs[idx]
            hits.append({
                "run_id": run_id,
                "score": round(-_neg, 6),
                "journal": d["journal"],
                "snippet": _best_text(d["texts"], terms),
            })
        return hits
