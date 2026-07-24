// Thin typed client over the MedIntel FastAPI backend.
// ponytail: bare fetch wrapper is enough for the scaffold; introduce TanStack
// Query (caching/retries/dedupe) when real data-fetching screens land, not now.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";
const TOKEN_KEY = "medintel_token";

/** Raised when the backend returns a non-2xx response. Carries the status + FastAPI's `detail`. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  // FormData/URLSearchParams set their own boundary/content-type — never override.
  if (init?.body !== undefined && !(init.body instanceof FormData) && !(init.body instanceof URLSearchParams)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body — fall through with no detail.
    }
    throw new ApiError(detail ?? `Request to ${path} failed (${response.status})`, response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Mirrors the backend `HealthResponse` contract (api/v1/health.py). */
export interface HealthStatus {
  status: string;
  version: string;
  environment: string;
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/health");
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

/** OAuth2PasswordRequestForm on the backend — form-encoded, field name is `username`. */
export function login(email: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body: new URLSearchParams({ username: email, password }),
  });
}

export type ValidationStatus = "pending" | "passed" | "failed";
export type VersionOrigin = "upload" | "cleaned";

export interface ValidationReport {
  failure_count: number;
  failures: Record<string, unknown>[];
  truncated?: boolean;
}

export interface DatasetVersion {
  id: string;
  version_number: number;
  parent_version_id: string | null;
  origin: VersionOrigin;
  checksum: string;
  size_bytes: number;
  row_count: number | null;
  column_names: string[] | null;
  validation_status: ValidationStatus;
  validation_report: ValidationReport | null;
  transformation: Record<string, unknown> | null;
  created_at: string;
}

export interface Dataset {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
  latest_version: DatasetVersion | null;
}

export interface DatasetDetail extends Dataset {
  versions: DatasetVersion[];
}

export function listDatasets(): Promise<Dataset[]> {
  return request<Dataset[]>("/datasets");
}

export function getDataset(id: string): Promise<DatasetDetail> {
  return request<DatasetDetail>(`/datasets/${id}`);
}

export function uploadDataset(name: string, file: File, description?: string): Promise<Dataset> {
  const body = new FormData();
  body.append("name", name);
  body.append("file", file);
  if (description) body.append("description", description);
  return request<Dataset>("/datasets", { method: "POST", body });
}
