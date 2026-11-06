/**
 * OpenAgent-X — TypeScript mirrors of schemas/*.json (JSON Schema draft 2020-12).
 * Keep this file in lockstep with the schemas; CI verifies JSON validity,
 * reviewes must keep both sides aligned. Generated validation code may replace
 * the manual mirrors later.
 */

// ---------- Task / Plan ----------

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type ModelProfile =
  | 'fast'
  | 'balanced'
  | 'reasoning'
  | 'coding'
  | 'vision'
  | 'local-private';

export interface SubtaskBudget {
  max_tokens: number;
  max_tool_calls: number;
  wall_time_seconds?: number;
}

export interface PlannedSubtask {
  subtask_id: string; // uuid
  objective: string;
  depends_on: string[]; // acyclic, references other subtask_ids
  agent_type: string;
  required_capabilities: string[];
  acceptance_criteria: string[];
  permission_scope: string[]; // default-deny; enforced by policy service
  budget: SubtaskBudget;
}

export interface TaskPlan {
  task_id: string; // uuid
  objective: string;
  assumptions?: string[];
  constraints?: { deadline: string | null; max_cost_usd?: number };
  risk_level: RiskLevel;
  subtasks: PlannedSubtask[];
  final_deliverables: string[];
}

// ---------- Agents ----------

export interface AgentBudget {
  tokens: number;
  tool_calls: number;
  wall_time_seconds: number;
}

export interface AgentDefinition {
  agent_id: string;
  version: string; // semver
  supported_task_types: string[];
  required_capabilities: string[];
  accepted_input_schema: object | string; // JSON Schema (inline or $ref)
  output_schema: object | string;
  allowed_tools: string[];
  default_model_profile: ModelProfile;
  max_budget: AgentBudget;
  permission_ceiling: string[];
  verification_policy: string[];
  runtime_adapter: 'native' | 'openhands' | 'agent-zero' | 'interpreter-workstation' | string;
}

export interface AgentTask {
  task_id: string;
  subtask_id: string;
  objective: string;
  project_id: string | null;
  context_refs?: string[]; // references, never inlined copies
  input_artifacts?: string[];
  required_capabilities: string[];
  permission_scope: string[];
  budget: SubtaskBudget;
  deadline?: string | null;
  acceptance_criteria: string[];
}

export interface AgentTestResult {
  name: string;
  passed: boolean;
  details?: string;
}

export interface AgentResult {
  task_id: string;
  subtask_id: string;
  status: 'completed' | 'partial' | 'failed' | 'blocked';
  summary: string;
  output_artifacts?: string[];
  evidence_refs?: string[];
  tests?: AgentTestResult[];
  errors?: string[];
  warnings?: string[];
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    tool_calls?: number;
    cost_usd?: number;
  };
  actual_model?: string | null; // real provider model/version, not alias
  runtime_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

// ---------- Events ----------

export type EventType =
  | 'task.created' | 'task.planned' | 'task.approval_requested' | 'task.approved' | 'task.started'
  | 'task.waiting_for_user' | 'task.blocked' | 'task.recovered' | 'task.completed' | 'task.failed' | 'task.cancelled'
  | 'subtask.dispatched' | 'subtask.completed' | 'subtask.failed'
  | 'agent.started' | 'agent.model_selected' | 'agent.tool_call.started' | 'agent.tool_call.completed'
  | 'execution.workspace_created' | 'execution.snapshot_created' | 'execution.terminated'
  | 'verification.started' | 'verification.passed' | 'verification.failed'
  | 'artifact.created' | 'artifact.downloaded'
  | 'memory.candidate_created' | 'memory.promoted';

export interface EventEnvelope {
  event_id: string;
  task_id: string | null;
  sequence: number; // monotonic per task
  event_type: EventType;
  occurred_at: string; // ISO-8601
  actor: { type: 'user' | 'agent' | 'system' | 'runtime' | 'policy'; id: string };
  correlation_id?: string | null;
  payload?: Record<string, unknown>; // secrets redacted before persistence
  redaction_applied?: boolean;
}

// ---------- Memory ----------

export interface MemoryRecord {
  memory_id: string;
  project_id: string | null; // null only for user-domain memories
  domain: 'project' | 'user' | 'knowledge' | 'execution' | 'task';
  type: 'decision' | 'fact' | 'preference' | 'procedure' | 'artifact_summary';
  content: string;
  source_refs?: string[]; // artifact:uuid, task:uuid, doc:span
  confidence?: number; // 0..1
  status: 'candidate' | 'verified' | 'superseded' | 'rejected';
  created_at: string;
  expires_at?: string | null;
  visibility: 'private' | 'project' | 'team';
}

// ---------- Approvals ----------

export interface Approval {
  approval_id: string;
  task_id: string;
  action_hash: string; // SHA-256 of the exact action/plan version
  approver_id?: string | null;
  decision: 'approved' | 'denied';
  created_at: string;
  expires_at: string;
  scope?: string;
}

// ---------- Task state machine ----------

export const TASK_STATES = [
  'CREATED', 'PLANNED', 'APPROVED', 'RUNNING', 'VERIFYING',
  'WAITING_FOR_USER', 'BLOCKED', 'RECOVERY', 'COMPLETED', 'FAILED', 'CANCELLED',
] as const;
export type TaskState = (typeof TASK_STATES)[number];

export const TRANSITIONS: Record<TaskState, TaskState[]> = {
  CREATED: ['PLANNED', 'CANCELLED', 'FAILED'],
  PLANNED: ['APPROVED', 'RUNNING', 'WAITING_FOR_USER'],
  APPROVED: ['RUNNING', 'CANCELLED'],
  RUNNING: ['VERIFYING', 'WAITING_FOR_USER', 'BLOCKED', 'FAILED', 'CANCELLED', 'RECOVERY'],
  VERIFYING: ['COMPLETED', 'RECOVERY', 'BLOCKED', 'FAILED'],
  WAITING_FOR_USER: ['APPROVED', 'RUNNING', 'CANCELLED'],
  BLOCKED: ['RUNNING', 'CANCELLED', 'FAILED'],
  RECOVERY: ['RUNNING', 'BLOCKED', 'FAILED'],
  COMPLETED: [],
  FAILED: [],
  CANCELLED: [],
};

// ---------- Permission tiers ----------

export const PERMISSION_TIERS = ['P0', 'P1', 'P2', 'P3', 'P4'] as const;
export type PermissionTier = (typeof PERMISSION_TIERS)[number];
