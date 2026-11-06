# ADR-008: Execution isolation and workspace lifecycle

**Decision:** Code/browser/data execution runs in containers/VMs (Docker sandbox first; VM/Kubernetes pools later) with non-root users, read-only base images, resource quotas, restricted egress, and per-task workspaces. Host desktop access is opt-in, read-only by default.

**Reason:** The system reads private files and executes code; isolation is the core safety boundary.

**Consequences:** Adapters must support create/inspect/pause/resume/terminate/snapshot where the runtime permits, and declare limitations otherwise.

**Operational impact:** No rollback promises for irreversible external effects; snapshot-before-destructive-edits is mandatory; cleanup on terminal states.
