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