import type {
  Agent,
  AgentInput,
  Run,
  RunDetail,
  Tool,
  Workflow,
  WorkflowInput,
} from "@/lib/types";

const RAW_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// All routers are mounted under the /api prefix in backend/app/main.py.
const API_BASE = `${RAW_BASE}/api`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      // Non-JSON error body; keep the status text.
    }
    throw new Error(detail);
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

// ---- Agents ----------------------------------------------------------------

export function listAgents(): Promise<Agent[]> {
  return request<Agent[]>("/agents");
}

export function createAgent(data: AgentInput): Promise<Agent> {
  return request<Agent>("/agents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateAgent(id: number, data: AgentInput): Promise<Agent> {
  return request<Agent>(`/agents/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function deleteAgent(id: number): Promise<void> {
  return request<void>(`/agents/${id}`, { method: "DELETE" });
}

// ---- Meta (tools + models) -------------------------------------------------

export function listTools(): Promise<Tool[]> {
  return request<Tool[]>("/tools");
}

export function listModels(): Promise<string[]> {
  return request<string[]>("/models");
}

// ---- Workflows -------------------------------------------------------------

export function listWorkflows(): Promise<Workflow[]> {
  return request<Workflow[]>("/workflows");
}

export function getWorkflow(id: number): Promise<Workflow> {
  return request<Workflow>(`/workflows/${id}`);
}

export function createWorkflow(data: WorkflowInput): Promise<Workflow> {
  return request<Workflow>("/workflows", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateWorkflow(
  id: number,
  data: Partial<WorkflowInput>,
): Promise<Workflow> {
  return request<Workflow>(`/workflows/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function runWorkflow(id: number, input: string): Promise<Run> {
  return request<Run>(`/workflows/${id}/run`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

// ---- Runs ------------------------------------------------------------------

export function listRuns(params?: {
  workflow_id?: number;
  limit?: number;
}): Promise<Run[]> {
  return request<Run[]>(`/runs${buildQuery(params ?? {})}`);
}

export function getRun(id: number): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${id}`);
}

// ---- Live stream helpers ---------------------------------------------------

export const api = {
  baseUrl: API_BASE,
  // Used by the EventSource in components/RunLogStream.tsx.
  streamUrl(runId: number): string {
    return `${API_BASE}/runs/${runId}/stream`;
  },
};
