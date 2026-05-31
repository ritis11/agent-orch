// Shared domain types for the frontend. These mirror the FastAPI/SQLModel
// response shapes defined in backend/app/models.py and the API routers.

export type Guardrails = {
  blocked_topics: string[];
  max_steps: number;
};

export type Agent = {
  id: number;
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  tools: string[];
  memory_window: number;
  temperature: number;
  max_tokens: number;
  // The backend defaults guardrails to an empty object, so inner fields may be absent.
  guardrails?: Partial<Guardrails>;
  schedule_cron: string | null;
  schedule_input: string | null;
  created_at?: string;
  updated_at?: string;
};

// Payload accepted by create/update agent endpoints.
export type AgentInput = {
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  tools: string[];
  memory_window: number;
  temperature: number;
  max_tokens: number;
  guardrails: Guardrails;
  schedule_cron: string | null;
  schedule_input: string | null;
};

export type Tool = {
  name: string;
  description?: string;
};

export type NodeKind = "start" | "agent" | "end";

export type GraphNode = {
  id: string;
  type: NodeKind;
  agent_id?: number;
  position?: { x: number; y: number };
};

export type GraphEdge = {
  id?: string;
  source?: string;
  target?: string;
  // Some payloads use from/to instead of source/target; support both.
  from?: string;
  to?: string;
  when?: string;
};

export type WorkflowGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type Workflow = {
  id: number;
  name: string;
  description: string;
  graph: WorkflowGraph;
  slack_channel: string | null;
  created_at?: string;
  updated_at?: string;
};

export type WorkflowInput = {
  name: string;
  description?: string;
  graph?: WorkflowGraph;
  slack_channel?: string | null;
};

// Note: the StatusBadge component keys its variant/label maps exhaustively on
// this union, so it must stay in sync with the values rendered there.
export type RunStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type RunTrigger = "manual" | "slack" | "schedule";

export type Run = {
  id: number;
  workflow_id: number;
  workflow_name?: string | null;
  status: RunStatus;
  trigger: RunTrigger | string;
  input: string;
  output?: string | null;
  error?: string | null;
  started_at: string;
  finished_at: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
};

export type MessageRole = "user" | "agent" | "tool" | "system" | string;

export type Message = {
  id: number;
  run_id: number;
  from_agent_id: number | null;
  from_agent_name?: string | null;
  to_agent_id: number | null;
  role: MessageRole;
  content: string;
  tokens_in: number;
  tokens_out: number;
  created_at: string;
};

export type LogLevel = "info" | "warn" | "error" | string;

export type LogEvent = {
  id: number;
  run_id: number;
  level: LogLevel;
  source: string;
  message: string;
  created_at: string;
};

// Returned by GET /api/runs/{id}
export type RunDetail = {
  run: Run;
  messages: Message[];
  logs: LogEvent[];
};
