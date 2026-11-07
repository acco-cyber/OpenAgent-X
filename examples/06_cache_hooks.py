"""Offline example 06 — cache + hooks: repeat prompts hit the store, deny
rules keep tools from ever running.

One scripted task is executed twice through a shared ``ResponseCache`` (the
second run's repeat prompts are served without touching the inner adapter),
and a second run carries a ``HookPolicy`` that denies ``calc`` — the decision
is journaled as a ``hook`` event, the tool never executes, and the agent
adapts and still replies.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.cache import CachedLLM, ResponseCache
from openagentx.events import sequence_dense
from openagentx.hooks import HookPolicy
from openagentx.llm import ScriptedLLM
from openagentx.runner import AgentRunner
from openagentx.tools import builtin_tools
from openagentx.trace import load_trace

SCRIPT = [
    '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "compute"}',
    '{"reply": "the answer is 42"}',
]
DENY_SCRIPT = [
    '{"action": {"tool": "echo", "args": {"text": "hello"}}, "thought": "echo first"}',
    '{"action": {"tool": "calc", "args": {"expr": "6*7"}}, "thought": "try the denied tool"}',
    '{"reply": "calc is unavailable, done anyway"}',
]


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-06-")

    # 1) cache: same task twice, one shared cache
    shared = ResponseCache()
    inners = []
    replies = []
    for i in range(2):
        inner = ScriptedLLM(list(SCRIPT))
        inners.append(inner)
        r = AgentRunner(CachedLLM(inner, shared), builtin_tools(wd),
                        os.path.join(wd, f"journal-{i}.jsonl"),
                        max_steps=6, workdir=wd,
                        run_id=f"cache-demo-{i}").run("compute 6*7")
        replies.append(r.reply)
    print(f"cache: replies={replies} stats={shared.stats()} "
          f"inner_calls={[c.calls for c in inners]}")

    # 2) hooks: deny calc, decisions journaled, run still replies
    jp = os.path.join(wd, "journal-hooks.jsonl")
    result = AgentRunner(ScriptedLLM(list(DENY_SCRIPT)), builtin_tools(wd), jp,
                         max_steps=6, workdir=wd, run_id="hooks-demo",
                         hooks=HookPolicy([
                             {"tool": "calc", "reason": "calc is disabled by policy"},
                             {"tool": "calc", "reason": "duplicate rule must never win"},
                         ])).run("echo, try calc, answer anyway")
    events, _torn = load_trace(jp)
    hooks = [e.payload for e in events if e.type == "hook"]
    denied_tool_ran = any(e.type in ("tool_call", "tool_result")
                          and (e.payload or {}).get("tool") == "calc"
                          for e in events)
    print(f"hooks: decisions={hooks}")
    print(f"hooks: stop={result.stop_reason} steps={result.steps}")

    assert replies[0] == replies[1] == "the answer is 42"
    assert shared.stats()["hits"] >= 1 and inners[1].calls == 0, \
        "the second run's repeats must be served from the cache"
    e1, _ = load_trace(os.path.join(wd, "journal-0.jsonl"))
    e2, _ = load_trace(os.path.join(wd, "journal-1.jsonl"))
    assert [e.type for e in e1] == [e.type for e in e2], "cached run journals identically"

    assert result.stop_reason == "reply" and result.steps == 3
    assert len(hooks) == 2
    assert hooks[0] == {"tool": "echo", "decision": "allow", "reason": ""}
    assert hooks[1] == {"tool": "calc", "decision": "deny",
                        "reason": "calc is disabled by policy"}, "first match wins"
    assert not denied_tool_ran, "denied tool never reaches the registry"
    assert sequence_dense(events)
    print("OK 06_cache_hooks (prompt-hash cache reuse, journaled deny policy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
