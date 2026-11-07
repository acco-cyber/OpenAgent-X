"""Prompt-hash response cache — deterministic, honest hits only.

The cache key is a SHA-256 over the *canonical JSON* of the exact message
list, so a hit can only ever serve the very prompt that produced the stored
turn: reordering content, adding a message, or changing a character changes
the key. Hits are returned as fresh copies (mutation cannot poison the
store), every lookup is counted (``hits``/``misses``), and an empty cache
invents nothing. The cache sits at the LLM-adapter layer: runners and
journals are untouched — a cached run journals exactly like a computed one.

Example:

    >>> k1 = prompt_key([{"role": "user", "content": "hi"}])
    >>> k1 == prompt_key([{"role": "user", "content": "hi"}])
    True
    >>> k1 == prompt_key([{"role": "user", "content": "hi!"}])
    False
"""

from __future__ import annotations

import copy
import hashlib
import json


def prompt_key(messages) -> str:
    """Canonical SHA-256 key for a message list (order-sensitive, exact)."""
    canonical = json.dumps(list(messages), sort_keys=True,
                           ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ResponseCache:
    """In-memory prompt-keyed turn store with honest hit/miss counters."""

    def __init__(self):
        self._store: dict = {}
        self.hits = 0
        self.misses = 0

    @property
    def size(self) -> int:
        return len(self._store)

    def lookup(self, messages):
        """Cached turn for this exact prompt, or None (and count it)."""
        hit = self._store.get(prompt_key(messages))
        if hit is None:
            self.misses += 1
            return None
        self.hits += 1
        return copy.deepcopy(hit)

    def store(self, messages, turn: dict) -> str:
        """Store a turn for its exact prompt; returns the key."""
        k = prompt_key(messages)
        self._store[k] = copy.deepcopy(dict(turn))
        return k

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "size": self.size}


class CachedLLM:
    """Adapter wrapper: serve exact-prompt repeats from the cache.

    On a hit the inner LLM is *not* called (its cursor/counter stays put —
    observable proof the answer came from the cache); on a miss the inner
    turn is computed once and stored.
    """

    def __init__(self, inner, cache: ResponseCache | None = None,
                 name: str = "cached"):
        self.inner = inner
        self.cache = cache if cache is not None else ResponseCache()
        self.name = name
        self.calls = 0  # calls that actually reached the inner adapter

    def complete(self, messages) -> dict:
        hit = self.cache.lookup(messages)
        if hit is not None:
            return hit
        self.calls += 1
        turn = self.inner.complete(messages)
        self.cache.store(messages, turn)
        return turn
