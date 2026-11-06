# 21. Release, open-source governance and GitHub growth

> Source: HYDRION ONE Complete Project Blueprint (v1.0) — Section 21. Adapted for OpenAgent-X.

## Public repository positioning

Recommended positioning: "OpenAgent-X is an open-source, model-agnostic AI operating system for verifiable agentic work." The README should immediately show what works today, a 60-90 second demo, architecture, quick start, security posture, benchmark status and roadmap.

## Minimum public repository contents

- README.md with one-sentence value proposition, GIF/video, architecture diagram and tested installation path.
- LICENSE selected after contribution and dependency review; do not choose a license only for marketing.
- SECURITY.md with private vulnerability reporting instructions.
- CONTRIBUTING.md and CODE_OF_CONDUCT.md.
- docs/architecture.md, docs/security.md, docs/operations.md and docs/development.md.
- Example projects and reproducible sample tasks.
- Evaluation report with exact versions and known failures.
- Issue templates: bug, feature, integration request, security issue (private channel), evaluation result.
- Release notes, checksums, SBOM and container image provenance.

## GitHub growth strategy

| Mechanism | Execution | Success signal |
|-----------|-----------|----------------|
| Show, do not claim | Publish short demonstrations of a complete workflow with visible tool trace and verified artifacts. | Users can reproduce the demo. |
| Research artifacts | Release benchmark suite, eval harness, task traces with sensitive data removed and ablation scripts. | External researchers run and cite the evaluation. |
| Integration ecosystem | Document provider, MCP and agent-runtime adapters with clear contribution guide. | Independent integration PRs and forks. |
| Build-in-public | Weekly changelog, roadmap updates, design decisions and failure writeups. | Returning contributors and meaningful discussions. |
| Onboarding | One-command local demo with mock provider and optional real API configuration. | First successful task and low setup friction. |
| Community | Respond to issues, label good first issues, publish contributor docs and keep milestones realistic. | Issue resolution time and contributor retention. |

## Launch sequence

1. Private alpha: founder and trusted collaborators run workflows and security tests.
2. Public technical preview: publish source, architecture and known limitations; default demo uses mock or safe tools.
3. v0.1 release: include the first end-to-end workflow, stable install, measured evaluation and documented security defaults.
4. v0.2: add memory quality improvements, more provider/runtime adapters and better local inference.
5. v1.0 only after stability, upgrade compatibility, backup/restore and clear support boundaries are demonstrated.

## Open-source licensing workflow

- Choose a project license after reviewing desired reuse, contribution model and dependency compatibility.
- Maintain THIRD_PARTY_NOTICES and machine-readable SBOM.
- For every upstream integration, record repository, version/commit, license, files copied, modifications and obligations.
- Review AGPL implications for MIRA before copying, modifying or distributing code or operating a modified network service.
- Check pinned submodules and transitive packages for Interpreter Workstation.
- Check individual OpenHands repositories/packages rather than assuming one license applies to all.
- Do not reuse names, logos or trademarks in a way that implies endorsement.
- Have qualified legal counsel review any commercial distribution or code derived from copyleft projects.
