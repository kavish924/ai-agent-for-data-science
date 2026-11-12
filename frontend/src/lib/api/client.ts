/**
 * Typed API client for the FastAPI backend (Spec 09). Types come from the generated
 * OpenAPI schema (`npm run gen:api`); requests go through the same-origin /api/v1 proxy.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];
export type Session = Schemas["SessionOut"];
export type Profile = Schemas["ProfileOut"];
export type ColumnProfile = Schemas["ColumnProfile"];
export type Plan = Schemas["PlanIn"];
export type PlanStep = Schemas["PlanStep"];
export type StepStatus = PlanStep["status"];
export type Op = PlanStep["op"];

export interface StepLogEntry {
  index: number;
  step_id: string | null;
  op: Op;
  column: string | null;
  status: "executed" | "disabled" | "failed" | "proposed";
  before?: { rows: number; cols: number; null_cells: number; outliers: number } | null;
  after?: { rows: number; cols: number; null_cells: number; outliers: number } | null;
  error?: string;
}

export interface ExecutionLog {
  status: "completed" | "failed";
  duration_ms: number;
  plan_version: number | null;
  error?: string;
  steps: StepLogEntry[];
}

export interface GateIssue {
  step: number;
  issue: string;
}

/** The backend's error envelope (FR-AP-08), surfaced with its user-presentable message. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Gate issues from a 422 `invalid_plan` response, if any (Spec 04 AC-8). */
  get gateIssues(): GateIssue[] {
    const issues = this.details?.issues;
    return Array.isArray(issues) ? (issues as GateIssue[]) : [];
  }
}

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the server. Is the backend running?");
  }
  if (!response.ok) {
    let body: { error?: { code?: string; message?: string; details?: Record<string, unknown> } } = {};
    try {
      body = await response.json();
    } catch {
      /* not JSON: fall through to a generic message */
    }
    throw new ApiError(
      response.status,
      body.error?.code ?? "http_error",
      body.error?.message ?? `Request failed (${response.status}).`,
      body.error?.details,
    );
  }
  return (await response.json()) as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  upload(file: File): Promise<Session> {
    const form = new FormData();
    form.append("file", file);
    return request("/sessions", { method: "POST", body: form });
  },
  session: (id: string) => request<Session>(`/sessions/${id}`),
  profile: (id: string) => request<Profile>(`/sessions/${id}/profile`),
  retryProfiling: (id: string) =>
    request<{ state: string }>(`/sessions/${id}/profile`, { method: "POST" }),
  setTarget: (id: string, target: string | null) =>
    request<Session>(`/sessions/${id}/target`, json("PUT", { target })),
  generatePlan: (id: string) => request<Plan>(`/sessions/${id}/plan`, { method: "POST" }),
  getPlan: (id: string) => request<Plan>(`/sessions/${id}/plan`),
  approve: (id: string, steps: PlanStep[]) =>
    request<Plan>(`/sessions/${id}/plan/approve`, json("POST", { steps })),
  execute: (id: string) =>
    request<{ state: string }>(`/sessions/${id}/execute`, { method: "POST" }),
  executionLog: (id: string) => request<ExecutionLog>(`/sessions/${id}/execution-log`),
  cleanedCsvUrl: (id: string) => `${BASE}/sessions/${id}/cleaned.csv`,
};
