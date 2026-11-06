# 6. Model gateway and capability-aware routing

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 6. Adapted for OpenAgent-X.

A unified model gateway is not only a provider proxy. It is a policy-aware selection layer that matches task requirements to actual model capabilities, availability, privacy constraints and operating cost. A provider gateway such as LiteLLM can handle broad API normalization, retries and deployment routing; OpenAgent-X should own task-level selection policy and the capability registry. [R8]

## Model registry schema

| Field | Examples / purpose |
| --- | --- |
| model_id | provider/model alias. Must identify the concrete deployment used for reproducibility. |
| provider | OpenAI, Anthropic, Google, local-vLLM, Ollama, OpenRouter or another supported provider. |
| capabilities | tool_calling, structured_output, long_context, vision, audio_in, audio_out, code, reasoning, embeddings. |
| limits | context window, max output, RPM/TPM, concurrency and provider-specific limits. |
| operational stats | p50/p95 latency, recent error rate, availability and time of last success. |
| cost profile | input/output token price, cached token price if applicable, image/audio pricing and currency/date basis. |
| data policy | region, retention assumptions, allowed data classification and local/private eligibility. |
| routing status | enabled, disabled, degraded, rate-limited or under evaluation. |
| evidence | benchmark results and date; never treat marketing labels as a measured score. |

## Capability-aware routing pipeline

1. Extract hard requirements from the task: tools, JSON schema, vision, audio, context, latency target, privacy and cost ceiling.
2. Filter out models that fail a hard requirement or violate the data policy.
3. Score the remaining models using task-specific evaluation evidence, availability, latency and expected cost.
4. Choose the best candidate, reserve a fallback and record why each candidate was accepted or rejected.
5. Call through the provider gateway with timeouts, retry policy and request metadata.
6. Record actual usage, latency, errors, output validity and quality signals. Update rolling estimates.

## Example routing objective

```
score(model, task) =
    w_cap * capability_fit(model, task)
  + w_quality * measured_quality(model, task.family)
  + w_avail * current_availability(model)
  + w_privacy * privacy_fit(model, task.data_class)
  - w_cost * normalized_cost(model, task.expected_tokens)
  - w_latency * normalized_latency(model, task.latency_target)
  - w_risk * operational_risk(model)

Selection rule:
  1. Apply hard capability and policy filters.
  2. Score only eligible candidates.
  3. Select highest score under the task budget.
  4. Use fallback only if it also satisfies hard constraints.
  5. Persist the decision and observed result.
```

The weights are configuration parameters to tune from evaluation data. They are not universal constants. Avoid optimizing only for cheapest-token or lowest-latency routing; tool reliability, structured-output validity, task success and data policy matter.

## Routing profiles

| Profile | Typical use | Routing emphasis |
| --- | --- | --- |
| fast | Classification, title extraction, simple transformations. | Low latency and cost; strict output validation. |
| balanced | Everyday planning, summarization and routine agent work. | Quality/cost balance and availability. |
| reasoning | Complex planning, mathematical reasoning and multi-step diagnosis. | Measured task quality, long context and tool control. |
| coding | Code understanding, patch generation and test repair. | Repository-level task success, coding tool support and context. |
| vision | Screenshots, charts, diagrams and document images. | Image input, resolution and visual QA performance. |
| local-private | Sensitive or offline-capable work. | Local endpoint, privacy boundary and feasible local capability. |

## Fallback and safety rules

- Do not silently switch to a model that lacks required vision, structured-output or tool-call capability.
- Do not send sensitive content to a fallback with a weaker data policy.
- For structured outputs, validate against JSON Schema and reject malformed data before dispatch.
- Log the real provider model/version, not only the friendly alias.
- Never include provider credentials in browser code, prompts or task artifacts.
- Maintain a test suite for provider quirks, streaming, tool calling, context overflow and timeout behavior.
