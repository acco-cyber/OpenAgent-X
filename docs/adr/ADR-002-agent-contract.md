# ADR-002: Agent contract independent of runtime

**Decision:** Agents are defined by the versioned AgentDefinition/AgentTask/AgentResult contract (schemas/), never by the runtime they execute on.

**Reason:** Swap frameworks (OpenHands, Agent Zero, Interpreter Workstation, native) without changing the planner or product UI.

**Consequences:** Runtimes are adapters; capability negotiation happens via the registry.

**Operational impact:** Adapter parity tests required; runtime-specific limits must be declared in the adapter, not assumed.
