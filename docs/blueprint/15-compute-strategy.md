# 15. DGX Spark and compute strategy

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 15. Adapted for OpenAgent-X.

The product should be model-agnostic and compute-aware. The laptop is a development console; DGX Spark is the preferred local inference and engineering compute node; cloud APIs and remote GPU instances are fallbacks for workloads that exceed local memory, performance or software compatibility. The official DGX Spark specification lists a Grace Blackwell system, 128 GB coherent unified system memory in the 128 GB configuration, 273 GB/s memory bandwidth and up to 1 PFLOP FP4 theoretical performance with sparsity. Actual model throughput depends on model architecture, quantization, context length, software stack and workload. [R14]

## Role allocation

| Resource | Use | Avoid |
| --- | --- | --- |
| Developer laptop (32 GB RAM, integrated graphics) | Editor, Git, browser, UI/API development, unit tests, docs, SSH and monitoring dashboards. | Assuming it can host large inference or multiple execution sandboxes. |
| DGX Spark | Local model serving, embeddings, evaluation jobs, code/data workloads that fit memory and supported software, private inference experiments. | Treating its theoretical FP4 number as guaranteed application throughput; exposing inference ports directly to the internet. |
| Cloud model APIs | High-quality reasoning, multimodal models and burst capacity. | Sending restricted project data without checking provider and data policy. |
| Remote GPU / cluster | Large models, large-batch evaluation, distributed training or workloads beyond DGX Spark. | Making Kubernetes/Ray mandatory for the MVP. |

## Compute scheduler inputs

- Required capability: text, vision, audio, embeddings, tool use, structured output.
- Model memory estimate and runtime compatibility.
- Available system memory / GPU memory, concurrency and queue depth.
- Task latency target, budget and expected tokens.
- Privacy classification and location/data-residency rule.
- Model health, quality evidence and benchmark history.
- Fallback endpoint and failure behavior.

## Local inference architecture

```
OpenAgent-X API / ORCHESTRATOR
        |
        v
MODEL ROUTER ---- cloud providers (policy-approved)
        |
        +---- DGX Spark gateway
                  |
                  +-- local model server (vLLM / supported runtime)
                  +-- embeddings service
                  +-- evaluation worker

Execution traffic is private-network only. Put model endpoints behind
an authenticated reverse proxy / network policy. Do not rely on a
single inference server API-key option as the complete security boundary.
```

## vLLM security caveat

vLLM documents an OpenAI-compatible HTTP server, but its own documentation warns that API-key authentication does not cover every endpoint. Deploy behind a reverse proxy, restrict network access, disable unused routes and test the actual version in use. [R15]

## Compute rollout

1. Start with cloud APIs and mock endpoints so application development is not blocked by GPU setup.
2. Bring up one local model endpoint on DGX Spark and register it with the same model gateway.
3. Run a capability smoke test: streaming, structured output, tool calling, context, concurrency and cancellation.
4. Benchmark per-task latency, tokens/sec, peak memory, quality and failure rate under realistic context lengths.
5. Add embeddings and evaluation workers only after stable inference is achieved.
6. Implement queue-based admission control and graceful fallback when local capacity is unavailable.
