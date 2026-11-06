# Schemas — Universal Contracts

JSON Schema (draft 2020-12) contracts for every moving part of OpenAgent-X. **Any AI system or runtime must validate payloads against these before emitting or accepting them.** TypeScript mirrors live in [`contracts/types.ts`](../contracts/types.ts).

| Schema | Validates | Used at boundary |
|---|---|---|
| [`plan.schema.json`](plan.schema.json) | Task Plan (planner output; decomposition, budgets, permissions, acceptance criteria) | orchestrator validates before dispatch |
| [`agent-definition.schema.json`](agent-definition.schema.json) | AgentDefinition registration | agent registry ingest |
| [`agent-task.schema.json`](agent-task.schema.json) | AgentTask work envelope | orchestrator → agent handoff |
| [`agent-result.schema.json`](agent-result.schema.json) | AgentResult (status, evidence, tests, usage) | agent → orchestrator return |
| [`event-envelope.schema.json`](event-envelope.schema.json) | Workflow event (append-only ledger) | every state transition / side effect |
| [`memory-record.schema.json`](memory-record.schema.json) | Memory record with provenance | memory service read/write |
| [`approval.schema.json`](approval.schema.json) | Persisted human approval (hash-bound) | policy service, P3+ gates |
| [`manifest.schema.json`](manifest.schema.json) | Repository manifest | tooling / AI bootstrap |

## Invariants encoded across schemas

1. **Budgets are mandatory** on every plan subtask and agent task (`max_tokens`, `max_tool_calls` at minimum).
2. **Acceptance criteria are mandatory** — nothing runs without checkable completion conditions.
3. **Permissions are explicit scopes**, enforced default-deny by the policy service (never by prompt).
4. **Evidence is mandatory for completion claims** (`evidence_refs` / `tests` in AgentResult).
5. **Status in AgentResult is a report, not authority** — the orchestrator owns task state.
6. **Approvals are hash-bound and expiring** — bound to the exact action/plan version.
7. **Events are append-only** with monotonic `sequence` and redaction flag.

## Usage example

```js
import Ajv from 'ajv';
const ajv = new Ajv({ allErrors: true });
const validate = ajv.compile(JSON.parse(await fs.readFile('schemas/plan.schema.json')));
if (!validate(plan)) throw new Error(`Invalid plan: ${ajv.errorsText(validate.errors)}`);
```
