# 24. Technical appendices and reference links

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 24. Adapted for OpenAgent-X.

## Appendix A: minimal environment configuration

```bash
# Example names only. Store actual secret values in a secrets manager.
APP_ENV=development
API_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql://hydrion:***@localhost:5432/hydrion
REDIS_URL=redis://localhost:6379/0
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_BUCKET=hydrion-artifacts
OIDC_ISSUER_URL=
OIDC_CLIENT_ID=
SECRET_MANAGER_BACKEND=local-dev-only
MODEL_GATEWAY_URL=http://localhost:4000
TEMPORAL_ADDRESS=localhost:7233
EXECUTION_BACKEND=docker
DEFAULT_TASK_BUDGET_USD=5
DEFAULT_MAX_TOOL_CALLS=30
ALLOW_HOST_COMPUTER_ACCESS=false
ALLOW_EXTERNAL_WRITES=false
```

The local-development secret backend must be clearly marked and must never be used in a production deployment. Commit only an `.env.example` with blank placeholders. (The `hydrion` database/bucket identifiers above are example names; an OpenAgent-X deployment may rename them.)

## Appendix B: initial acceptance suite

| Test ID | Scenario | Expected result |
|---------|----------|-----------------|
| T-001 | Create task with valid objective. | Task ID returned; CREATED event persisted. |
| T-002 | Planner emits malformed plan. | Plan rejected; no agent dispatched. |
| T-003 | Agent requests tool outside allowlist. | Invocation denied by policy service and audited. |
| T-004 | P3 external action without approval. | Blocked; no network side effect occurs. |
| T-005 | P3 action approved for a different payload hash. | Approval rejected as non-matching. |
| T-006 | Provider timeout. | Bounded retry/fallback; failure reason visible. |
| T-007 | Worker crashes after event persistence. | Workflow resumes or safely reconciles without duplicate side effect. |
| T-008 | Project A user queries Project B memory. | No Project B content returned. |
| T-009 | Verifier finds failed acceptance criterion. | Task does not transition to COMPLETED. |
| T-010 | User cancels during code execution. | Cancellation propagates; workspace cleanup and audit event occur. |
| T-011 | Artifact is changed after completion. | Checksum mismatch detected. |
| T-012 | DGX Spark endpoint becomes unavailable. | Allowed fallback or waiting state; local-only task remains blocked. |

## Appendix C: required architecture decision records

- ADR-001: canonical orchestration and event ownership.
- ADR-002: model gateway and routing ownership.
- ADR-003: authorization, approval token and risk taxonomy.
- ADR-004: execution isolation and workspace lifecycle.
- ADR-005: PostgreSQL/pgvector and memory retention.
- ADR-006: external runtime adapters and version compatibility.
- ADR-007: source/license policy and third-party notices.
- ADR-008: deployment boundaries and DGX Spark networking.
- ADR-009: model/data privacy classes and provider eligibility.
- ADR-010: benchmark protocol and public reporting requirements.

## Appendix D: key external references

The following primary project and documentation pages were reviewed for this blueprint. GitHub default branches and documentation evolve; pin exact versions/commits and re-check license and deployment instructions before implementation or release.

- [R1] OpenAgent repository README and feature overview — <https://github.com/the-open-agent/openagent>
- [R2] MIRA repository README, architecture and AGPL-3.0 notice — <https://github.com/Vexillon-ai/MIRA>
- [R3] OpenHands Agent Canvas repository and current component boundaries — <https://github.com/OpenHands/OpenHands>
- [R4] OpenHands Software Agent SDK and Agent Server documentation — <https://github.com/OpenHands/software-agent-sdk>
- [R5] OpenHands Software Agent SDK MIT license file — <https://github.com/OpenHands/software-agent-sdk/blob/main/LICENSE>
- [R6] Agent Zero repository, project docs and MIT license statement — <https://github.com/agent0ai/agent-zero>
- [R7] Interpreter Workstation repository, architecture and Apache 2.0 license note — <https://github.com/openinterpreter/interpreter-workstation>
- [R8] LiteLLM routing and load-balancing documentation — <https://docs.litellm.ai/docs/routing>
- [R9] Model Context Protocol specification — <https://modelcontextprotocol.io/specification/>
- [R10] MCP authorization specification (2025-11-25) — <https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization>
- [R11] Agent2Agent Protocol specification — <https://a2a-protocol.org/v1.0.1/specification/>
- [R12] Temporal Python SDK developer guide — <https://docs.temporal.io/develop/python>
- [R13] OpenTelemetry Python documentation — <https://opentelemetry.io/docs/languages/python/>
- [R14] NVIDIA DGX Spark official specifications — <https://www.nvidia.com/en-us/products/workstations/dgx-spark/>
- [R15] vLLM OpenAI-compatible server and API-key security caveat — <https://docs.vllm.ai/en/latest/serving/openai_compatible_server/>
- [R16] SWE-bench — <https://www.swebench.com/>
- [R17] GAIA benchmark — <https://huggingface.co/gaia-benchmark>
- [R18] WebArena — <https://webarena.dev/>
- [R19] OSWorld — <https://os-world.github.io/>
- [R20] Terminal-Bench — <https://terminal-bench.com/>
- [R21] BrowseComp — <https://browsecomp.github.io/>

## Final recommendation

BUILD THIS FIRST: Ship a single safe, durable and verifiable workflow before expanding the system: submit an objective -> create a plan -> approve it -> delegate research or coding -> execute through one isolated runtime -> verify evidence/tests -> generate artifacts -> persist the complete trace. That vertical slice is the foundation for every later capability.

End of blueprint. Document status: proposed plan. Implementation status and benchmark outcomes must be updated as evidence becomes available.
