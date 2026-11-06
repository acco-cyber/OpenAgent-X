# 16. Monorepo structure and engineering standards

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 16. Adapted for OpenAgent-X.

Use a monorepo initially so API contracts, migrations, frontend, orchestration and tests evolve together. Keep external runtimes independently versioned and accessed through APIs or thin adapters. Split repositories only when ownership, deployment or contribution scale requires it.

## Monorepo tree

```
openagent-x/
  apps/
    web/                    # Next.js user interface
    desktop/                # Tauri shell (later)
    cli/                    # Optional operator/developer CLI
    admin/                  # Admin and observability UI
  services/
    api/                    # FastAPI public/internal APIs
    orchestrator/           # Durable workflows and planning
    model_gateway/          # Provider proxy + OpenAgent-X router
    agent_registry/         # Versioned agent definitions
    memory/                 # Memory and knowledge API
    tool_gateway/           # MCP clients, tool policy mediation
    execution/              # Sandbox lifecycle and runtime adapters
    artifacts/              # Artifact metadata and object-store access
    scheduler/              # Compute admission and queue policy
  agents/
    research/ coding/ data/ mathematics/ science/
    browser/ writing/ memory/ qa/
  integrations/
    providers/ openhands/ agent_zero/
    interpreter_workstation/ openagent/ mira/
    mcp/ a2a/ github/ notifications/
  packages/
    contracts/ schemas/ api_client/ ui_components/
    policy_sdk/ telemetry_sdk/ test_fixtures/
  security/
    auth/ policy/ secrets/ sandbox/ audit/
  evaluation/
    datasets/ harnesses/ task_suites/ reports/
  infrastructure/
    docker/ compose/ dgx_spark/ monitoring/ deployment/
  docs/
    architecture/ adr/ security/ operations/ research/
  scripts/ tests/ migrations/
  .github/ README.md CONTRIBUTING.md SECURITY.md LICENSE
```

## Engineering conventions

- Typed interfaces and schema validation at all service boundaries.
- Version every agent definition, tool adapter, model deployment alias and event schema.
- Keep business logic out of API route handlers.
- Use database migrations with rollback notes and integration tests.
- Use structured logging with task_id, project_id, trace_id and actor_id; redact secrets and private payloads.
- Add unit tests for policy decisions and state transitions; integration tests for runtime behavior.
- Every new external integration includes timeout, retry, rate limit, health check and license/security review.
- Pin dependencies and container digests for releases; generate SBOM and release checksums.
- Use feature flags for risky or incomplete capabilities.
- Document operational impact and failure modes in every architecture decision record.

## Branch and release pattern

Use short-lived feature branches, reviewed pull requests, required CI, signed version tags and conventional release notes. Avoid direct pushes to the protected main branch. Every PR should reference an issue or planned acceptance criterion and include tests, screenshots for UI changes, migration impact and risk notes.
