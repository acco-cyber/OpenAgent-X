# 7. Agent workforce and collaboration model

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 7. Adapted for OpenAgent-X.

Agents are specialist execution profiles, not independent sovereign assistants. Every agent runs under the same task ID, project scope, permission service, budget ledger and audit rules. Agent roles should be few and clear at first; a generic worker can be more useful than an unmaintainable list of narrow personas.

## Agent roles

| Agent | Responsibilities | Typical tools | Verification requirement |
| --- | --- | --- | --- |
| Master / orchestrator | Own task graph and workflow; not a free-form worker. | Planner, registry, workflow engine. | Plan schema, policy checks, state invariants. |
| Research | Find, inspect, compare and synthesize sources. | Search, fetch, browser, PDF/document parsing. | Source relevance, dates, claims-to-citations map. |
| Coding | Modify repository and run scoped checks. | Git, file APIs, shell, test runner via sandbox. | Diff review, tests, static checks, dependency review. |
| Data | Profile data, build analysis pipeline, generate artifacts. | Python/R, notebook runner, SQL, object storage. | Schema checks, reproducibility, leakage checks, sanity tests. |
| Mathematics / science | Formalize problems, derive and test technical claims. | CAS, Python, literature tools, code execution. | Independent derivation, numerical checks, assumptions. |
| Browser / computer | Operate websites and desktop software within approved scope. | Browser automation, screenshots, controlled desktop bridge. | Action preconditions, screenshots, final state confirmation. |
| Writing | Turn verified inputs into structured documents. | Document generation, templates, artifact store. | Consistency with evidence, format and completeness checks. |
| Memory curator | Extract candidate project facts and decisions. | Memory APIs, project wiki, entity resolution. | Provenance, confidence, scope and user correction path. |
| QA / verifier | Independently test outputs against acceptance criteria. | Tests, browser review, citation checker, schema validators. | Must not merely echo the producing agent; use separate evidence. |

## Agent contract

```
AgentDefinition = {
  agent_id: string,
  version: semver,
  supported_task_types: string[],
  required_capabilities: string[],
  accepted_input_schema: JSONSchema,
  output_schema: JSONSchema,
  allowed_tools: string[],
  default_model_profile: string,
  max_budget: { tokens, tool_calls, wall_time_seconds },
  permission_ceiling: string[],
  verification_policy: string[],
  runtime_adapter: string
}
```

```
AgentTask = {
  task_id, subtask_id, objective, project_id,
  context_refs, input_artifacts,
  required_capabilities, permission_scope,
  budget, deadline, acceptance_criteria
}
```

```
AgentResult = {
  task_id, subtask_id, status, summary,
  output_artifacts, evidence_refs, tests,
  errors, warnings, usage, actual_model,
  runtime_id, started_at, completed_at
}
```

## Collaboration rules

- Pass references to artifacts rather than copying huge context between agents.
- Every handoff states objective, accepted inputs, output schema, dependencies, constraints and acceptance criteria.
- The receiving agent sees only necessary context and authorized artifact references.
- Agent messages and outputs are untrusted data; they cannot change permissions or system policy.
- The verifier should be selected independently of the producer when feasible.
- Limit agent-to-agent chat; structured handoffs are easier to audit and replay.
