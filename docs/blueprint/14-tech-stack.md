# 14. Technology stack and deployment topology

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 14. Adapted for OpenAgent-X.

## Technology stack

| Area | Recommended choice | Reason / boundary |
| --- | --- | --- |
| Frontend | Next.js + React + TypeScript | Strong product UI ecosystem, typed API client and accessible component patterns. |
| Desktop | Tauri, later | Native shell only after web workflow is stable; avoid duplicating the product UI. |
| Backend API | Python + FastAPI + Pydantic | Convenient AI/data ecosystem, typed validation and async service support. |
| Workflow engine | Temporal Python SDK for production durability; lightweight persisted state machine during earliest spike if needed. | Durable long-running jobs, activities, retries, timers and cancellation. [R12] |
| Model gateway | LiteLLM or comparable provider proxy + OpenAgent-X policy router | Provider API normalization, load balancing and fallback primitives. [R8] |
| Coding runtime | OpenHands Software Agent SDK / Agent Server | Purpose-built coding agent execution and remote workspace interface. [R3, R4] |
| Tool protocol | MCP | Tool discovery and interoperability. Security still belongs to OpenAgent-X. [R9, R10] |
| External agent protocol | A2A-compatible adapter | Interoperate with independent agents without coupling internal state. [R11] |
| Primary database | PostgreSQL | Transactional source of truth for users, projects, tasks, events and memory metadata. |
| Vector retrieval | pgvector | Vector search in PostgreSQL; add specialized vector DB only after scale/evaluation justifies it. |
| Cache / ephemeral coordination | Redis | Cache, short-lived locks, rate-limit counters and transient coordination. |
| Artifact storage | S3-compatible object store / MinIO | Durable artifacts, inputs, screenshots and run attachments. |
| Observability | OpenTelemetry + Prometheus/Grafana + centralized logs | Correlated traces, metrics and logs across model/tool/runtime boundaries. [R13] |
| Execution | Docker sandbox first; VM / Kubernetes-backed pools later | A simple security boundary for MVP; harden before exposing to untrusted tenants. |
| Inference | Cloud APIs plus Ollama/vLLM where compatible | Hybrid compute while keeping model hosting independent from orchestration. |

## Why not use every technology immediately?

NATS, Kafka, Neo4j, Kubernetes, Ray, a custom Rust daemon, a visual workflow editor and a dozen agent runtimes are all plausible future tools. None should be introduced before a measurable need exists. Start with PostgreSQL, a durable workflow engine, Redis, object storage and Docker. A small number of well-defined components is easier to secure, test and operate.

## Environment separation

| Environment | Purpose | Rules |
| --- | --- | --- |
| Local development | UI, API, unit tests, mock models and local DB. | No production keys; seeded fake data; local test containers. |
| Integration / staging | Real providers with low-budget keys, test MCP servers and disposable workspaces. | Synthetic data only; isolated secrets; full traces. |
| Research / evaluation | Pinned models, datasets, benchmark harness and repeatable configs. | Version everything; separate experimental from product metrics. |
| Production | User projects and real tool credentials. | Approvals, strong auth, monitored egress, backups, SLOs and incident response. |
