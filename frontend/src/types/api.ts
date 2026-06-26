export type HealthResponse = {
  service: string;
  version: string;
  environment: string;
  api_status: string;
  database_status: string;
};

export type OverviewResponse = {
  devices: {
    total: number;
    online: number;
    offline: number;
  };
  metrics: {
    total: number;
  };
  alerts: {
    unresolved: number;
  };
  recovery_actions: {
    total: number;
  };
};

export type Device = {
  id?: string;
  device_id?: string;
  hostname: string;
  ip_address: string;
  os_name: string;
  status?: string;
  last_seen?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type Alert = {
  id?: string;
  alert_id?: string;
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
  level?: string;
  message?: string;
  reason?: string;
  reasons?: string[];
  cpu_percent?: number;
  memory_percent?: number;
  disk_percent?: number;
  unresolved_alerts?: number;
  calculated_at?: string;
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