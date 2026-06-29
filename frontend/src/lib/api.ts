import { authStorage } from "./authStorage";
import type {
  Alert,
  AlertRule,
  AuditLog,
  AuthResponse,
  AuthUser,
  CreateAlertRulePayload,
  CreateDeviceCredentialPayload,
  CreatedDeviceCredential,
  CreateIncidentEventPayload,
  CreateIncidentPayload,
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
    let errorDetails = "";

    try {
      const errorBody = await response.json();
      errorDetails = JSON.stringify(errorBody);
    } catch {
      errorDetails = await response.text();
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

async function readErrorDetails(response: Response) {
  try {
    const errorBody = await response.json();
    return JSON.stringify(errorBody);
  } catch {
    return response.text();
  }
}

async function loginWithFallback(payload: LoginPayload): Promise<AuthResponse> {
  const email = payload.email.trim();

  const jsonResponse = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password: payload.password,
    }),
  });

  if (jsonResponse.ok) {
    return jsonResponse.json() as Promise<AuthResponse>;
  }

  const jsonErrorDetails = await readErrorDetails(jsonResponse);

  const formBody = new URLSearchParams();
  formBody.set("username", email);
  formBody.set("email", email);
  formBody.set("password", payload.password);

  const formResponse = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formBody,
  });

  if (formResponse.ok) {
    return formResponse.json() as Promise<AuthResponse>;
  }

  const formErrorDetails = await readErrorDetails(formResponse);

  throw new ApiError(
    formResponse.status,
    formResponse.statusText,
    formErrorDetails || jsonErrorDetails,
  );
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

  getAuditLogs: (
    params: { limit?: number; severity?: string; action?: string } = {},
  ) => request<AuditLog[]>(`/audit-logs${buildQuery(params)}`),

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
