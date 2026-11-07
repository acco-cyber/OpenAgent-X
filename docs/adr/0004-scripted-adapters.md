# ADR-0004 — Scripted, offline LLM adapters are the default; the adapter is the boundary

## Status

Accepted

## Context

Tests that call a real model are flaky, slow, expensive, and
unreproducible: the same prompt can answer differently a second later, so
no assertion about agent behavior can be firm. But a framework tested only
against mocks lies to itself — mocks that bypass the real interface prove
nothing about it.

## Decision

`llm.py` defines the adapter boundary (`complete(messages) -> turn`) and
ships deterministic adapters as first-class citizens: `ScriptedLLM` (a list
of JSON turns, consumed in order, with observable `.cursor` and `.calls`)
and `EchoLLM`. Every golden drill, every example, and the default dev loop
runs on scripted adapters, so runs are byte-for-byte reproducible and
stop reasons (`reply`, `max_steps`, `budget`, `script_error`) are testable
contracts rather than observations of fortune. A real model adapter would
be a thin `complete()` implementation at this same boundary — everything
upstream (runner, hooks, cache, retry, breaker, JIT) is adapter-agnostic
and already proven against the contract.

## Consequences

Positive: the golden matrix (35 tasks, 399 checks) runs in seconds, fully
offline, with assertions strong enough to compare event streams; failures
reproduce forever; scripted exhaustion is distinguishable from budget
exhaustion and from a step cap.

Negative: scripted tests never prove what a real model would do — prompt
quality, latency, cost are out of scope by construction; the JSON-turn
script format is one more mini-format contributors must learn; there is a
standing temptation to treat green drills as proof of model behavior,
which they are not and claim not to be.
