import { authStorage } from "./authStorage";
import type {
  Alert,
  AlertRule,
  AuditLog,
  SecurityLog,
  AuthResponse,
  AuthUser,
  CreateAlertRulePayload,
  CreateDeviceCredentialPayload,
  CreatedDeviceCredential,
  CreateIncidentEventPayload,
  CreateIncidentPayload,
  CreateRecoveryActionPayload,
  CreateUserPayload,
  Device,
  DeviceCredential,
  DeviceHealth,
  DeviceSummary,
  HealthResponse,
  Incident,
  IncidentEvent,
  LoginPayload,
  OverviewResponse,
  RecoveryAction,
  SignupPayload,
  SystemMetric,
  UpdateAlertRulePayload,
  UpdateUserPayload,
  UpdateUserRolePayload,
  UpdateUserSettingsPayload,
  UserSettings,
} from "../types/api";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  status: number;
  statusText: string;
  details: string;

  constructor(status: number, statusText: string, details: string) {
    const fallback = status === 429
      ? "Too many requests. Please wait a moment before trying again."
      : details || "Unexpected API error.";

    super(fallback);

    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.details = details;
  }
}

function normaliseErrorDetails(errorBody: unknown): string {
  if (!errorBody) return "";

  if (typeof errorBody === "string") return errorBody;

  if (typeof errorBody === "object" && errorBody !== null) {
    const maybeDetail = (errorBody as { detail?: unknown }).detail;

    if (typeof maybeDetail === "string") {
      return maybeDetail;
    }

    if (Array.isArray(maybeDetail)) {
      return maybeDetail
        .map((entry) => {
          if (typeof entry === "string") return entry;
          if (typeof entry === "object" && entry !== null) {
            const message = (entry as { msg?: unknown }).msg;
            const location = (entry as { loc?: unknown }).loc;
            const locationText = Array.isArray(location) ? location.join(".") : "field";
            return typeof message === "string" ? `${locationText}: ${message}` : JSON.stringify(entry);
          }
          return String(entry);
        })
        .join("; ");
    }

    const message = (errorBody as { message?: unknown }).message;
    if (typeof message === "string") {
      return message;
    }
  }

  try {
    return JSON.stringify(errorBody);
  } catch {
    return "Unexpected API error.";
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
};

async function request<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const token = authStorage.getToken();

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };

  if (options.auth !== false && token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let errorDetails: string;

    try {
      const errorBody = await response.json();
      errorDetails = normaliseErrorDetails(errorBody);
    } catch {
      errorDetails = await response.text();
    }

    if (response.status === 429 && !errorDetails) {
      errorDetails = "Too many requests. Please wait before trying again.";
    }

    if (response.status === 401) {
      authStorage.clearToken();
    }

    throw new ApiError(response.status, response.statusText, errorDetails);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return response.json() as Promise<TResponse>;
}

function buildQuery(
  params: Record<string, string | number | boolean | undefined>,
) {
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
  getHealth: () => request<HealthResponse>("/health", { auth: false }),
  getOverview: () => request<OverviewResponse>("/overview"),

  login: (payload: LoginPayload) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: {
        email: payload.email.trim(),
        password: payload.password,
      },
      auth: false,
    }),

  signup: (payload: SignupPayload) =>
    request<AuthResponse>("/auth/signup", {
      method: "POST",
      body: payload,
      auth: false,
    }),

  getMe: () => request<AuthUser>("/auth/me"),

  logout: () =>
    request<{ message?: string }>("/auth/logout", {
      method: "POST",
    }),

  getUsers: () => request<AuthUser[]>("/users"),
  createUser: (payload: CreateUserPayload) =>
    request<AuthUser>("/users", { method: "POST", body: payload }),
  getUser: (userId: string) =>
    request<AuthUser>(`/users/${encodeURIComponent(userId)}`),
  updateUser: (userId: string, payload: UpdateUserPayload) =>
    request<AuthUser>(`/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: payload,
    }),
  updateUserRole: (userId: string, payload: UpdateUserRolePayload) =>
    request<AuthUser>(`/users/${encodeURIComponent(userId)}/role`, {
      method: "PATCH",
      body: payload,
    }),
  deactivateUser: (userId: string) =>
    request<AuthUser>(`/users/${encodeURIComponent(userId)}/deactivate`, {
      method: "PATCH",
    }),

  getMySettings: () => request<UserSettings>("/user-settings/me"),
  updateMySettings: (payload: UpdateUserSettingsPayload) =>
    request<UserSettings>("/user-settings/me", {
      method: "PATCH",
      body: payload,
    }),

  getDeviceCredentials: () =>
    request<DeviceCredential[]>("/device-credentials"),
  createDeviceCredential: (payload: CreateDeviceCredentialPayload) =>
    request<CreatedDeviceCredential>("/device-credentials", {
      method: "POST",
      body: payload,
    }),
  revokeDeviceCredential: (credentialId: string) =>
    request<DeviceCredential>(
      `/device-credentials/${encodeURIComponent(credentialId)}/revoke`,
      {
        method: "PATCH",
      },
    ),

  getDevices: () => request<Device[]>("/devices"),
  getDevice: (deviceId: string) =>
    request<Device>(`/devices/${encodeURIComponent(deviceId)}`),

  setDeviceStatus: (deviceId: string, enabled: boolean) =>
    request<Device>(`/devices/${encodeURIComponent(deviceId)}/status`, {
      method: "PATCH",
      body: { enabled },
    }),

  getAlerts: () => request<Alert[]>("/alerts"),
  resolveAlert: (alertId: string) =>
    request<Alert>(`/alerts/${encodeURIComponent(alertId)}/resolve`, {
      method: "PATCH",
    }),

  getRecoveryActions: () => request<RecoveryAction[]>("/recovery-actions"),

  createRecoveryAction: (payload: CreateRecoveryActionPayload) =>
    request<RecoveryAction>("/recovery-actions", {
      method: "POST",
      body: payload,
    }),

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

  getAuditLogs: (
    params: { limit?: number; severity?: string; action?: string } = {},
  ) => request<AuditLog[]>(`/audit-logs${buildQuery(params)}`),

  getSecurityLogs: (
    params: { limit?: number; severity?: string; event_type?: string; status_value?: string } = {},
  ) => request<SecurityLog[]>(`/security-logs${buildQuery(params)}`),

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
