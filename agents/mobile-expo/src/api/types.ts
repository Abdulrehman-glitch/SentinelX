// Mirrors backend/app/schemas/* — snake_case comes straight off the wire.

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  organization_id: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface Device {
  id: string;
  organization_id: string | null;
  hostname: string;
  display_name: string | null;
  ip_address: string | null;
  os_name: string | null;
  device_type: string;
  agent_type: string;
  agent_version: string | null;
  status: string;
  last_seen_at: string | null;
  created_at: string;
}

export interface Metric {
  id: string;
  organization_id: string;
  device_id: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  recorded_at: string;
}

export interface Alert {
  id: string;
  organization_id: string | null;
  device_id: string;
  alert_type: string;
  severity: string;
  message: string;
  resolved: boolean;
  created_at: string;
  resolved_at: string | null;
}

export interface Incident {
  id: string;
  organization_id: string | null;
  device_id: string | null;
  title: string;
  description: string | null;
  severity: string;
  status: string;
  source: string;
  linked_alert_id: string | null;
  assigned_to: string | null;
  created_at: string;
  updated_at: string | null;
  resolved_at: string | null;
}

export interface IncidentEvent {
  id: string;
  incident_id: string;
  event_type: string;
  message: string;
  actor_type: string;
  actor_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface IncidentDetail extends Incident {
  events: IncidentEvent[];
}

export interface AuditLog {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  severity: string;
  message: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface RecoveryAction {
  id: string;
  organization_id: string | null;
  device_id: string;
  action_type: string;
  status: string;
  details: string | null;
  created_at: string;
}

export interface DeviceHealth {
  device_id: string;
  hostname: string;
  device_status: string;
  health_score: number;
  health_status: string;
  last_seen_at: string | null;
  latest_metric: Metric | null;
  unresolved_warning_alerts: number;
  unresolved_critical_alerts: number;
  reasons: string[];
  evaluated_at: string;
}

export interface DeviceSummaryCounts {
  metrics: number;
  heartbeats: number;
  alerts_total: number;
  alerts_unresolved: number;
  recovery_actions: number;
}

export interface DeviceSummary {
  device: Device;
  latest_metric: Metric | null;
  recent_metrics: Metric[];
  recent_alerts: Alert[];
  recent_recovery_actions: RecoveryAction[];
  health: DeviceHealth;
  counts: DeviceSummaryCounts;
}

export interface Overview {
  devices: { total: number; online: number; offline: number };
  metrics: { total: number };
  alerts: { unresolved: number };
  recovery_actions: { total: number };
  incidents: { total: number; open: number; investigating: number; resolved: number };
  audit_logs: { total: number };
  alert_rules: { total: number; enabled: number; disabled: number };
}

export interface Heartbeat {
  id: string;
  organization_id: string;
  device_id: string;
  status: string;
  message: string | null;
  recorded_at: string;
}

export interface DeviceCredentialCreated {
  id: string;
  organization_id: string | null;
  device_id: string | null;
  name: string;
  token: string;
  token_preview: string;
  is_active: boolean;
  created_at: string;
}

export interface DeviceRegisterRequest {
  hostname: string;
  display_name?: string;
  ip_address?: string | null;
  os_name?: string | null;
  organization_slug?: string | null;
  device_type?: string;
  agent_type?: string;
  agent_version?: string | null;
}

export interface HeartbeatRequest {
  device_id: string;
  status: string;
  message?: string | null;
}

export interface IncidentCreateRequest {
  device_id?: string | null;
  title: string;
  description?: string | null;
  severity?: "info" | "warning" | "critical";
  source?: "manual" | "alert" | "system";
  linked_alert_id?: string | null;
  assigned_to?: string | null;
}

export interface IncidentEventCreateRequest {
  event_type: string;
  message: string;
  actor_type?: "system" | "agent" | "user";
  actor_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface RecoveryActionCreateRequest {
  device_id: string;
  action_type: string;
  status?: string;
  details?: string | null;
}
