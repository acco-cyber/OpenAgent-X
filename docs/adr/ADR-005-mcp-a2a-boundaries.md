# ADR-005: MCP for tools, A2A for external agents

**Decision:** Adopt MCP for tool discovery/invocation and A2A for delegating to independent agent systems. Both are boundaries, not security models.

**Reason:** Reuse standards at the edges without ceding authorization.

**Consequences:** MCP servers/tools are allowlisted per project, pinned, schema-validated, risk-classed. External A2A agents are translated into the internal AgentTask/AgentResult contract with identical policy, budget, timeout, verification gates.

**Operational impact:** Tool results are untrusted prompt-injection surfaces; invocation audit logs server identity, tool name, redacted args, approval ID.
