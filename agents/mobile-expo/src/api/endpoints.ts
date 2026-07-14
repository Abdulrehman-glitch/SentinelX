import { request } from "./client";
import type {
  Alert,
  AuditLog,
  Device,
  DeviceCredentialCreated,
  DeviceHealth,
  DeviceRegisterRequest,
  DeviceSummary,
  Heartbeat,
  HeartbeatRequest,
  Incident,
  IncidentCreateRequest,
  IncidentDetail,
  IncidentEvent,
  IncidentEventCreateRequest,
  LoginResponse,
  Metric,
  Organization,
  Overview,
  RecoveryAction,
  RecoveryActionCreateRequest,
  UserPublic,
} from "./types";

export const sentinelxApi = {
  // auth
  login: (email: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: "none",
      authRequest: true,
    }),
  me: () => request<UserPublic>("/auth/me"),
  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),

  // org
  myOrganization: () => request<Organization>("/organizations/me"),

  // overview
  overview: () => request<Overview>("/overview"),

  // devices
  devices: () => request<Device[]>("/devices"),
  device: (id: string) => request<Device>(`/devices/${id}`),
  deviceHealth: (id: string) => request<DeviceHealth>(`/devices/${id}/health`),
  deviceSummary: (id: string) => request<DeviceSummary>(`/devices/${id}/summary`),
  deviceMetricHistory: (id: string, limit = 60) =>
    request<Metric[]>(`/devices/${id}/metrics/history?limit=${limit}`),
  registerDevice: (payload: DeviceRegisterRequest) =>
    request<Device>("/devices/register", { method: "POST", body: payload, auth: "none" }),
  deleteDevice: (id: string) => request<void>(`/devices/${id}`, { method: "DELETE" }),

  // device credentials (admin+)
  createDeviceCredential: (deviceId: string, name: string) =>
    request<DeviceCredentialCreated>("/device-credentials", {
      method: "POST",
      body: { device_id: deviceId, name },
    }),
  revokeDeviceCredential: (credentialId: string) =>
    request<unknown>(`/device-credentials/${credentialId}/revoke`, { method: "PATCH" }),

  // alerts
  alerts: (params?: { unresolvedOnly?: boolean; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.unresolvedOnly) search.set("unresolved_only", "true");
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return request<Alert[]>(`/alerts${qs ? `?${qs}` : ""}`);
  },
  resolveAlert: (id: string) => request<Alert>(`/alerts/${id}/resolve`, { method: "PATCH" }),

  // incidents
  incidents: (params?: { status?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status_filter", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return request<Incident[]>(`/incidents${qs ? `?${qs}` : ""}`);
  },
  incident: (id: string) => request<IncidentDetail>(`/incidents/${id}`),
  incidentEvents: (id: string) => request<IncidentEvent[]>(`/incidents/${id}/events`),
  createIncident: (payload: IncidentCreateRequest) =>
    request<Incident>("/incidents", { method: "POST", body: payload }),
  addIncidentEvent: (id: string, payload: IncidentEventCreateRequest) =>
    request<IncidentEvent>(`/incidents/${id}/events`, { method: "POST", body: payload }),
  updateIncidentStatus: (id: string, status: "open" | "investigating" | "resolved") =>
    request<Incident>(`/incidents/${id}/status`, { method: "PATCH", body: { status } }),
  resolveIncident: (id: string) => request<Incident>(`/incidents/${id}/resolve`, { method: "PATCH" }),

  // activity
  auditLogs: (limit = 100) => request<AuditLog[]>(`/audit-logs?limit=${limit}`),

  // recovery
  recoveryActions: (limit = 50) => request<RecoveryAction[]>(`/recovery-actions?limit=${limit}`),
  createRecoveryAction: (payload: RecoveryActionCreateRequest) =>
    request<RecoveryAction>("/recovery-actions", { method: "POST", body: payload }),

  // health probe (unauthenticated)
  health: () => request<{ status: string }>("/health", { auth: "none", timeoutMs: 8_000 }),

  // agent-facing (device token)
  sendHeartbeat: (payload: HeartbeatRequest, deviceToken: string) =>
    request<Heartbeat>("/heartbeats", {
      method: "POST",
      body: payload,
      auth: "device",
      deviceToken,
    }),
};
