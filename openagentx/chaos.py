"""Chaos engineering for one run — combined, deterministic, fully ledgered.

Real incidents never arrive one at a time: the model endpoint blips *while*
a tool is also misbehaving. :mod:`openagentx.chaos` injects **several fault
classes into the same run** on a fixed, inspectable plan, so the resilience
layers (retry, honest tool envelopes, journaling) can be observed under
combined stress — offline and reproducibly.

Contracts:

- **Deterministic plans**: :class:`ChaosLLM` fails exactly the 1-based
  ``complete()`` call numbers named in its plan; :class:`ChaosTools` fails
  the first *n* calls of each named tool. Same plan in, same faults out —
  no randomness anywhere.
- **Every injection is ledgered**: both wrappers append one entry per
  injected fault to ``injected`` (kind, target, detail). Recovery shows its
  scars; nothing is injected silently.
- **Injected tool faults never execute**: the wrapped registry is consulted
  only for a *planned* pass-through. A faulted call returns the honest
  ``{"ok": False, "error": "chaos: ..."}`` envelope with zero side effects —
  no file writes, no registry execution.
- **Loud misconfiguration**: a chaos plan naming an unknown tool raises
  ``ValueError`` naming it (mirrors the JIT policy contract).
- **Composable**: ``ChaosLLM`` is an adapter (wrap it in ``RetryLLM`` to
  recover); ``ChaosTools`` quacks like a registry (``call``/``names``/
  ``schemas``), so the runner cannot tell it apart — which is the point.
"""

from __future__ import annotations

from .llm import LLMUnavailable
from .tools import ToolError, ToolRegistry

FAULT_TOOL = "tool_fault"
FAULT_LLM = "llm_outage"


class ChaosLLM:
    """Fail exactly the planned ``complete()`` call numbers, pass the rest."""

    def __init__(self, inner, plan: dict = None, name: str = "chaos-llm"):
        self.inner = inner
        plan = dict(plan or {})
        cleaned = {}
        for k, v in plan.items():
            n = int(k)
            if n < 1:
                raise ValueError(f"chaos plan call numbers are 1-based; got {n}")
            cleaned[n] = str(v)
        self.plan = cleaned
        self.name = name
        self.calls = 0
        self.injected: list = []

    def complete(self, messages) -> dict:
        self.calls += 1
        if self.calls in self.plan:
            why = self.plan[self.calls]
            self.injected.append({
                "kind": FAULT_LLM,
                "call": self.calls,
                "error": why,
            })
            raise LLMUnavailable(f"chaos outage at call {self.calls}: {why}")
        return self.inner.complete(messages)


class ChaosTools:
    """Fail the first *n* calls of each planned tool; pass everything else.

    Faulted calls never reach the wrapped registry: the honest failure
    envelope is returned directly, so a faulted write leaves no file behind.
    """

    def __init__(self, registry: ToolRegistry, plan: dict = None,
                 name: str = "chaos-tools"):
        self.registry = registry
        plan = dict(plan or {})
        known = set(registry.names())
        for tool, n in plan.items():
            if tool not in known:
                raise ValueError(f"unknown chaos target tool '{tool}'")
            if int(n) < 1:
                raise ValueError(f"chaos plan for '{tool}' must fail >= 1 call")
        self.plan = {str(t): int(n) for t, n in plan.items()}
        self.name = name
        self.seen: dict = {}
        self.injected: list = []

    def names(self) -> list:
        return self.registry.names()

    def call(self, name: str, args: dict) -> dict:
        if name in self.plan:
            k = self.seen.get(name, 0) + 1
            self.seen[name] = k
            if k <= self.plan[name]:
                self.injected.append({
                    "kind": FAULT_TOOL,
                    "tool": name,
                    "call": k,
                })
                return {"ok": False,
                        "error": f"chaos: fault {k}/{self.plan[name]} on {name}"}
        return self.registry.call(name, args)

    def passthrough_calls(self) -> int:
        """Fault-planned calls that went through to the real registry."""
        total = 0
        for tool, n in self.plan.items():
            total += max(0, self.seen.get(tool, 0) - n)
        return total

    def summary(self) -> dict:
        """Deterministic fault counts over this wrapper's ledger."""
        return chaos_summary(self.injected)


def chaos_summary(ledger: list) -> dict:
    """Sorted kind→count map over a chaos ledger (deterministic)."""
    counts: dict = {}
    for entry in ledger:
        kind = str(entry.get("kind", ""))
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))
