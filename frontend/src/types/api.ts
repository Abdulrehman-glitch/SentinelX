export type HealthResponse = {
  service: string;
  version: string;
  environment: string;
  api_status: string;
  database_status: string;
};

export type OverviewResponse = {
  devices: { total: number; online: number; offline: number };
  metrics: { total: number };
  alerts: { unresolved: number };
  recovery_actions: { total: number };
  incidents?: { total: number; open: number; investigating: number; resolved: number };
  audit_logs?: { total: number };
  alert_rules?: { total: number; enabled: number; disabled: number };
};

export type Device = {
  id?: string;
  device_id?: string;
  organization_id?: string | null;
  hostname: string;
  display_name?: string | null;
  ip_address?: string | null;
  os_name?: string | null;
  device_type?: string;
  agent_type?: string;
  agent_version?: string | null;
  status?: string;
  last_seen_at?: string | null;
  last_seen?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type Alert = {
  id?: string;
  alert_id?: string;
  organization_id?: string | null;
  device_id?: string;
  alert_type?: string;
  metric_type?: string;
  severity: string;
  message: string;
  resolved?: boolean;
  is_resolved?: boolean;
  created_at?: string;
  updated_at?: string;
  resolved_at?: string | null;
};

export type RecoveryAction = {
  id?: string;
  recovery_action_id?: string;
  organization_id?: string | null;
  device_id?: string;
  action_type: string;
  status: string;
  details?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type SystemMetric = {
  id?: string;
  metric_id?: string;
  device_id?: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  // Mobile-agent extras; null/absent for desktop agents.
  battery_percent?: number | null;
  battery_charging?: boolean | null;
  network_transport?: string | null;
  latency_ms?: number | null;
  created_at?: string;
  updated_at?: string;
  recorded_at?: string;
  timestamp?: string;
};

export type DeviceHealth = {
  device_id?: string;
  health_score?: number;
  score?: number;
  status?: string;
  health_status?: string;
  device_status?: string;
  level?: string;
  message?: string;
  reason?: string;
  reasons?: string[];
  cpu_percent?: number;
  memory_percent?: number;
  disk_percent?: number;
  unresolved_alerts?: number;
  unresolved_warning_alerts?: number;
  unresolved_critical_alerts?: number;
  calculated_at?: string;
  evaluated_at?: string;
  last_seen_at?: string | null;
  latest_metric?: SystemMetric | null;
};

export type DeviceSummary = {
  device?: Device;
  latest_metrics?: SystemMetric | null;
  latest_metric?: SystemMetric | null;
  health?: DeviceHealth;
  recent_alerts?: Alert[];
  alerts?: Alert[];
  recent_recovery_actions?: RecoveryAction[];
  recovery_actions?: RecoveryAction[];
};

export type AuditLog = {
  id: string;
  organization_id?: string | null;
  actor_type: string;
  actor_id?: string | null;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  severity: string;
  message: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
};


export type SecurityLog = {
  id: string;
  event_type: string;
  severity: string;
  actor_type: string;
  actor_id?: string | null;
  ip_address?: string | null;
  organization_id?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  status: string;
  message: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
};

export type Incident = {
  id: string;
  organization_id?: string | null;
  device_id?: string | null;
  title: string;
  description?: string | null;
  severity: string;
  status: string;
  source: string;
  linked_alert_id?: string | null;
  assigned_to?: string | null;
  created_at: string;
  updated_at?: string;
  resolved_at?: string | null;
};

export type AnomalyFeatureComparisonEntry = {
  baseline?: number | null;
  actual: number;
  z_score?: number | null;
  is_affected?: boolean | null;
};

export type ReviewStatus =
  | "unreviewed"
  | "true_positive"
  | "false_positive"
  | "expected_change"
  | "insufficient_context";

export type AnomalyPrediction = {
  id: string;
  organization_id: string;
  device_id: string;
  feature_window_id: string;
  model_name: string;
  model_version: string;
  feature_schema_version: string;
  anomaly_score: number;
  threshold: number;
  is_anomalous: boolean;
  confidence: "low" | "medium" | "high";
  feature_comparison: Record<string, AnomalyFeatureComparisonEntry>;
  explanation: string;
  shadow_mode: boolean;
  review_status: ReviewStatus;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  created_at: string;
};

export type RecoveryCommandStatus =
  | "proposed"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "expired"
  | "dispatched"
  | "acknowledged"
  | "running"
  | "succeeded"
  | "failed"
  | "verifying"
  | "verified"
  | "ineffective"
  | "inconclusive"
  | "rolled_back";

export type RecoveryCommand = {
  id: string;
  organization_id?: string | null;
  device_id: string;
  incident_id?: string | null;
  alert_id?: string | null;
  anomaly_prediction_id?: string | null;
  action_type: string;
  parameters_json: Record<string, unknown>;
  risk_level: string;
  reason?: string | null;
  decision_source: string;
  confidence?: number | null;
  status: RecoveryCommandStatus;
  approval_mode: string;
  approved_by?: string | null;
  approved_at?: string | null;
  command_nonce?: string | null;
  payload_hash?: string | null;
  signature?: string | null;
  expires_at?: string | null;
  created_at: string;
  dispatched_at?: string | null;
  acknowledged_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  result_code?: string | null;
  result_message?: string | null;
  result_data_json?: Record<string, unknown> | null;
  pre_action_snapshot_json?: Record<string, unknown> | null;
  post_action_snapshot_json?: Record<string, unknown> | null;
  verification_status?: string | null;
  verification_message?: string | null;
  model_name?: string | null;
  model_version?: string | null;
  policy_id?: string | null;
};

export type RecoveryCommandEvent = {
  id: string;
  command_id: string;
  organization_id?: string | null;
  event_type: string;
  previous_status?: string | null;
  new_status?: string | null;
  actor_type: string;
  actor_id?: string | null;
  message?: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
};

export type CreateRecoveryCommandPayload = {
  device_id: string;
  action_type: string;
  parameters?: Record<string, unknown>;
  reason?: string | null;
};

export type ProposeRecoveryFromAnomalyPayload = {
  action_type: string;
  parameters?: Record<string, unknown>;
};

export type AnomalyModelInfo = {
  id: string;
  name: string;
  version: string;
  device_class: string;
  feature_schema_version: string;
  algorithm: string;
  hyperparameters: Record<string, unknown>;
  dataset_hash: string;
  code_commit?: string | null;
  trained_at: string;
  artifact_path?: string | null;
  is_active: boolean;
  created_at: string;
};

export type DeviceRunResult = {
  device_id: string;
  device_class: string | null;
  windows_built: number;
  windows_scored: number;
  predictions_created: number;
  errors: string[];
  skipped_reason: string | null;
};

export type PipelineRunResult = {
  devices_processed: number;
  windows_built: number;
  windows_scored: number;
  predictions_created: number;
  device_results: DeviceRunResult[];
};

export type ReviewAnomalyPredictionPayload = {
  review_status: ReviewStatus;
  review_note?: string | null;
};

export type IncidentEvent = {
  id: string;
  incident_id: string;
  event_type: string;
  message: string;
  actor_type: string;
  actor_id?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
};

export type AlertRule = {
  id: string;
  organization_id?: string | null;
  name: string;
  metric_type: string;
  operator: string;
  threshold: number;
  severity: string;
  enabled: boolean;
  description?: string | null;
  cooldown_seconds: number;
  created_at: string;
  updated_at?: string;
};

export type CreateIncidentPayload = {
  device_id?: string | null;
  title: string;
  description?: string | null;
  severity: string;
  source: string;
  linked_alert_id?: string | null;
  assigned_to?: string | null;
};

export type CreateIncidentEventPayload = {
  event_type: string;
  message: string;
  actor_type: string;
  actor_id?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type CreateAlertRulePayload = {
  name: string;
  metric_type: string;
  operator: string;
  threshold: number;
  severity: string;
  enabled: boolean;
  description?: string | null;
  cooldown_seconds: number;
  device_id?: string | null;
};

export type UpdateAlertRulePayload = Partial<CreateAlertRulePayload>;

export type UserRole =
  | "platform_admin"
  | "owner"
  | "admin"
  | "engineer"
  | "operator"
  | "viewer";

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  organization_id?: string | null;
  created_at?: string;
  updated_at?: string;
  last_login_at?: string | null;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type SignupPayload = {
  email: string;
  full_name: string;
  password: string;
  role?: UserRole;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export type UpdateUserPayload = {
  full_name?: string;
  is_active?: boolean;
};

export type UpdateUserRolePayload = {
  role: UserRole;
};

export type CreateUserPayload = {
  full_name: string;
  email: string;
  password: string;
  role: "owner" | "admin" | "engineer" | "operator" | "viewer";
};

export type UserSettings = {
  id?: string;
  user_id?: string;
  theme: "dark" | "light" | "system";
  density: "comfortable" | "compact";
  font_size: "normal" | "large";
  reduce_motion: boolean;
  high_contrast: boolean;
  color_blind_mode: boolean;
  table_page_size: number;
  auto_refresh_seconds: number;
  created_at?: string;
  updated_at?: string;
};

export type UpdateUserSettingsPayload = Partial<UserSettings>;

export type DeviceCredential = {
  id: string;
  organization_id?: string | null;
  device_id?: string | null;
  name: string;
  token_preview: string;
  is_active: boolean;
  created_at: string;
  revoked_at?: string | null;
};

export type CreateDeviceCredentialPayload = {
  name: string;
  device_id?: string | null;
};

export type CreatedDeviceCredential = DeviceCredential & {
  token: string;
};

export type CreateRecoveryActionPayload = {
  device_id: string;
  action_type: string;
  status: string;
  details?: string | null;
};
