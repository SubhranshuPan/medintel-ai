// Thin typed client over the MedIntel FastAPI backend.
// ponytail: bare fetch wrapper is enough for the scaffold; introduce TanStack
// Query (caching/retries/dedupe) when real data-fetching screens land, not now.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

/** Raised when the backend returns a non-2xx response. Carries the status code. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed (${response.status})`, response.status);
  }
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
