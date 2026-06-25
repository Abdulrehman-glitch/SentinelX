import type {
  Alert,
  Device,
  HealthResponse,
  OverviewResponse,
  RecoveryAction,
} from "../types/api";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  status: number;
  statusText: string;
  details: string;

  constructor(status: number, statusText: string, details: string) {
    super(
      `Request failed: ${status} ${statusText}${
        details ? ` - ${details}` : ""
      }`,
    );

    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.details = details;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
};

async function request<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let errorDetails = "";

    try {
      const errorBody = await response.json();
      errorDetails = JSON.stringify(errorBody);
    } catch {
      errorDetails = await response.text();
    }

    throw new ApiError(response.status, response.statusText, errorDetails);
  }

  return response.json() as Promise<TResponse>;
}

export const sentinelxApi = {
  getHealth: () => request<HealthResponse>("/health"),
  getOverview: () => request<OverviewResponse>("/overview"),
  getDevices: () => request<Device[]>("/devices"),
  getAlerts: () => request<Alert[]>("/alerts"),
  getRecoveryActions: () => request<RecoveryAction[]>("/recovery-actions"),
  resolveAlert: (alertId: string) =>
    request<Alert>(`/alerts/${alertId}/resolve`, {
      method: "PATCH",
    }),
};