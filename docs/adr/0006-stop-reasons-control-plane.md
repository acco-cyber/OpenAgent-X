# ADR-0006 — Four stop reasons; control-plane is never a tool call

## Status

Accepted

## Context

A loop that can only "finish" hides how it finished — and agent failures
are mostly about *how* a run ended: did the model answer, did it run out
of room, did policy stop it, did it choose to stop? Treating the stop tool
or a team handoff as an ordinary tool call pollutes the tool budget and
lets bookkeeping look like work.

## Decision

A run ends in exactly one of four named ways, carried by `run_end`:
`reply` (the agent answered), `max_steps` (the step cap hit — never a
fabricated reply), `budget` (the tool-call governor stopped the loop
*before* the rejected call, with a `budget` event naming the tool, the cap
recorded at `run_start`, executed calls all preceding the budget line), and
`stop` (the agent called the reserved `stop` tool with an explicit,
reasoned stop). `stop` and the team `handoff` are control-plane: reserved,
never journaled as tool calls, budget-free; a handoff switches the active
role and hands delegated context through the one shared journal. Script
exhaustion (`ScriptExhausted`) is a fourth-party fact — a plan bug, not a
stop reason — and surfaces as `script_error`.

## Consequences

Positive: stop reasons are a closed set, so drills can assert exactly which
one happened and why; the budget line names its refusal with used/cap;
control-plane actions can never eat the budget or fake productivity.

Negative: a closed set means new end-states require an ADR-grade decision
and drill updates; distinguishing "the script ran out" from "the agent
chose to stop" is on contributors, because the journal will not blur them
for you.
