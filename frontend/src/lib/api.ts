import type {
  Alert,
  AlertRule,
  AuditLog,
  CreateAlertRulePayload,
  CreateIncidentEventPayload,
  CreateIncidentPayload,
  Device,
  DeviceHealth,
  DeviceSummary,
  HealthResponse,
  Incident,
  IncidentEvent,
  OverviewResponse,
  RecoveryAction,
  SystemMetric,
  UpdateAlertRulePayload,
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

function buildQuery(params: Record<string, string | number | boolean | undefined>) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();

  return query ? `?${query}` : "";
}

export const sentinelxApi = {
  getHealth: () => request<HealthResponse>("/health"),
  getOverview: () => request<OverviewResponse>("/overview"),

  getDevices: () => request<Device[]>("/devices"),
  getDevice: (deviceId: string) =>
    request<Device>(`/devices/${encodeURIComponent(deviceId)}`),

  getAlerts: () => request<Alert[]>("/alerts"),
  resolveAlert: (alertId: string) =>
    request<Alert>(`/alerts/${encodeURIComponent(alertId)}/resolve`, {
      method: "PATCH",
    }),

  getRecoveryActions: () => request<RecoveryAction[]>("/recovery-actions"),

  getDeviceLatestMetrics: (deviceId: string) =>
    request<SystemMetric | null>(
      `/devices/${encodeURIComponent(deviceId)}/metrics/latest`,
    ),

  getDeviceMetricHistory: (deviceId: string, limit = 100) =>
    request<SystemMetric[]>(
      `/devices/${encodeURIComponent(deviceId)}/metrics/history?limit=${limit}`,
    ),

  getDeviceHealth: (deviceId: string) =>
    request<DeviceHealth>(`/devices/${encodeURIComponent(deviceId)}/health`),

  getDeviceSummary: (deviceId: string) =>
    request<DeviceSummary>(`/devices/${encodeURIComponent(deviceId)}/summary`),

  getAuditLogs: (params: { limit?: number; severity?: string; action?: string } = {}) =>
    request<AuditLog[]>(`/audit-logs${buildQuery(params)}`),

  getIncidents: () => request<Incident[]>("/incidents"),
  getIncident: (incidentId: string) =>
    request<Incident>(`/incidents/${encodeURIComponent(incidentId)}`),
  createIncident: (payload: CreateIncidentPayload) =>
    request<Incident>("/incidents", {
      method: "POST",
      body: payload,
    }),
  updateIncidentStatus: (incidentId: string, status: string) =>
    request<Incident>(`/incidents/${encodeURIComponent(incidentId)}/status`, {
      method: "PATCH",
      body: { status },
    }),
  resolveIncident: (incidentId: string) =>
    request<Incident>(`/incidents/${encodeURIComponent(incidentId)}/resolve`, {
      method: "PATCH",
    }),

  getIncidentEvents: (incidentId: string) =>
    request<IncidentEvent[]>(
      `/incidents/${encodeURIComponent(incidentId)}/events`,
    ),
  createIncidentEvent: (
    incidentId: string,
    payload: CreateIncidentEventPayload,
  ) =>
    request<IncidentEvent>(
      `/incidents/${encodeURIComponent(incidentId)}/events`,
      {
        method: "POST",
        body: payload,
      },
    ),

  getAlertRules: () => request<AlertRule[]>("/alert-rules"),
  createAlertRule: (payload: CreateAlertRulePayload) =>
    request<AlertRule>("/alert-rules", {
      method: "POST",
      body: payload,
    }),
  updateAlertRule: (ruleId: string, payload: UpdateAlertRulePayload) =>
    request<AlertRule>(`/alert-rules/${encodeURIComponent(ruleId)}`, {
      method: "PATCH",
      body: payload,
    }),
  toggleAlertRule: (ruleId: string) =>
    request<AlertRule>(`/alert-rules/${encodeURIComponent(ruleId)}/toggle`, {
      method: "PATCH",
    }),
};