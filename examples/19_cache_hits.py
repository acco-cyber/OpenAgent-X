"""Offline example 19 — cache hits: prompt-hash responses, honestly counted.

The cache key is a SHA-256 over the canonical JSON of the *exact*
message list — reordering, adding a message or changing a character
changes the key, so a hit can only serve the very prompt that produced
the stored turn. On a hit the inner LLM is not called at all (its
call counter stays put — observable proof the answer came from the
cache), and the cache sits at the LLM layer: the runner and journal are
untouched, so a cached run journals exactly like a computed one. This
example runs the same script twice through a shared cache, proves the
second run never reaches the inner adapter while the two journals diff
as SAME, then attacks the key (order/content sensitivity) and the store
(mutation safety, empty-cache honesty).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.cache import CachedLLM, ResponseCache, prompt_key
from openagentx.jdiff import diff_journals
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools

SCRIPT = [
    '{"action": {"tool": "think", "args": {"note": "cache me"}}, "thought": "plan"}',
    '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
    '{"reply": "cached and identical"}',
]


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-19-")
    task = "serve my turns from cache"

    # 1) first run: every lookup is a miss, the inner LLM computes everything
    cache = ResponseCache()
    a_llm = CachedLLM(ScriptedLLM(SCRIPT), cache)
    jp_a = os.path.join(wd, "a.jsonl")
    r1 = AgentRunner(a_llm, builtin_tools(wd), jp_a, max_steps=8,
                     workdir=wd, run_id="cache-demo").run(task)
    s1 = cache.stats()
    if not (s1["hits"] == 0 and s1["misses"] == 3 and s1["size"] == 3
            and a_llm.calls == 3):
        raise SystemExit(f"first-run stats are not honest: {s1}, calls={a_llm.calls}")
    if r1.reply != "cached and identical":
        raise SystemExit(f"unexpected reply: {r1.reply!r}")
    print(f"run 1: {s1['misses']} misses / {s1['hits']} hits, "
          f"inner adapter called {a_llm.calls}x")

    # 2) second run, same script, SAME cache: every lookup hits, the inner
    #    adapter is never called — observable proof of a cache-served run
    b_llm = CachedLLM(ScriptedLLM(SCRIPT), cache)
    jp_b = os.path.join(wd, "b.jsonl")
    r2 = AgentRunner(b_llm, builtin_tools(os.path.join(wd, "wd2")),
                     jp_b, max_steps=8, workdir=os.path.join(wd, "wd2"),
                     run_id="cache-demo").run(task)
    s2 = cache.stats()
    if not (s2["hits"] == 3 and s2["misses"] == 3 and b_llm.calls == 0):
        raise SystemExit(f"second run did not come from the cache: {s2}")
    if r2.reply != r1.reply:
        raise SystemExit("cached reply differs from the computed one")
    print(f"run 2: {s2['hits']} hits / {s2['misses']} new misses, "
          f"inner adapter called {b_llm.calls}x")

    # 3) the cache sits at the LLM layer: the two journals are identical
    d = diff_journals(jp_a, jp_b)
    if not d["same"] or d["diverged_at"] != -1:
        raise SystemExit("a cached run does not journal like a computed one")
    print(f"journals: SAME ({d['common']} events — the cache never touches "
          "the runner or the journal)")

    # 4) key sensitivity: content and order both change the key
    k1 = prompt_key([{"role": "user", "content": "a"}])
    k2 = prompt_key([{"role": "user", "content": "b"}])
    k3 = prompt_key([{"role": "user", "content": "a"},
                     {"role": "user", "content": "b"}])
    k4 = prompt_key([{"role": "user", "content": "b"},
                     {"role": "user", "content": "a"}])
    if len({k1, k2, k3, k4}) != 4:
        raise SystemExit("prompt keys collide on content or order")
    print("key: sha256 over canonical JSON — a character or an order "
          "change is a different key")

    # 5) mutation safety: hits are fresh copies, the store cannot be poisoned
    small = ResponseCache()
    small.store([{"x": 1}], {"reply": "truth"})
    t1 = small.lookup([{"x": 1}])
    t1["reply"] = "poisoned"
    t2 = small.lookup([{"x": 1}])
    if t2["reply"] != "truth" or small.lookup([{"x": 1}])["reply"] != "truth":
        raise SystemExit("a mutated hit poisoned the store")
    if t1 is t2:
        raise SystemExit("hits are not fresh copies")

    # 6) empty-cache honesty: a miss invents nothing
    fresh = ResponseCache()
    if fresh.lookup([{"x": 1}]) is not None or fresh.stats()["misses"] != 1:
        raise SystemExit("an empty cache must miss honestly")

    print("OK 19_cache_hits (hits serve only the exact prompt that produced"
          " them, the inner adapter's counter proves where each answer came"
          " from, cached and computed runs journal identically, and neither"
          " mutation nor an empty store can fake a hit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
