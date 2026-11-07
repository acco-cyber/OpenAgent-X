"""Offline example 11 — JIT tool disclosure: the model only sees what the
policy revealed.

Turn zero journals the visible set (core tools + the ``tools_expand`` control
plane). A scripted agent tries ``calc`` before any rule fired: refused with
one ``tool_hidden`` event and zero side effects. It requests the schema
through ``tools_expand`` — an ordinary journaled call — which makes ``calc``
visible, and the second ``calc`` executes. A vault tool whose keywords never
surfaced stays hidden the whole run. Every visibility change lands in the
journal as ``tool_disclose`` with the full visible set and what was added.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.events import Journal
from openagentx.jit import JITAgentRunner, JITDisclosure, DisclosureRule
from openagentx.llm import ScriptedLLM
from openagentx.tools import builtin_tools


def main() -> int:
    workdir = tempfile.mkdtemp(prefix="oax-example-11-")
    registry = builtin_tools(workdir)
    disclosure = JITDisclosure(
        registry,
        rules=[DisclosureRule(("arithmetic", "sum"), ("calc",)),
               DisclosureRule(("vault", "credential"), ("vault_read", "vault_bundle"))],
        always=("think",),
    )
    llm = ScriptedLLM([
        {"thought": "calc should still be hidden",
         "action": {"tool": "calc", "args": {"expr": "6*7"}}},
        {"thought": "request the schema through the control plane",
         "action": {"tool": "tools_expand", "args": {"tool": "calc"}}},
        {"thought": "calc is visible now",
         "action": {"tool": "calc", "args": {"expr": "6*7"}}},
        {"thought": "vault keywords never surfaced",
         "action": {"tool": "vault_read", "args": {"key": "github"}}},
        {"reply": "visibility stayed honest: nothing was used before it was disclosed"},
    ])
    runner = JITAgentRunner(llm, registry, os.path.join(workdir, "journal.jsonl"),
                            disclosure=disclosure, max_steps=8, run_id="ex11")
    result = runner.run("begin quietly")

    print(f"stop_reason={result.stop_reason} steps={result.steps} events={result.events}")
    events = Journal(result.journal_path).events()
    for ev in events:
        if ev.type in ("tool_disclose", "tool_hidden", "tool_call", "tool_result"):
            payload = json.dumps(ev.payload, sort_keys=True)
            print(f"  {ev.type:<14} {payload[:100]}")

    assert result.stop_reason == "reply"
    discloses = [e.payload for e in events if e.type == "tool_disclose"]
    hiddens = [e.payload["tool"] for e in events if e.type == "tool_hidden"]
    assert discloses[0]["disclosed"] == ["think", "tools_expand"]
    assert hiddens == ["calc", "vault_read"]
    assert discloses[-1]["added"] == ["calc"]
    calc = [e.payload for e in events if e.type == "tool_result" and e.payload.get("tool") == "calc"]
    assert calc and calc[0]["result"]["value"] == 42
    assert all("vault" not in p["disclosed"] for p in discloses)

    print("OK 11_tools_jit (hidden calls refused, expansion journaled, "
          "visibility timeline deterministic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
