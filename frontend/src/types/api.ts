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