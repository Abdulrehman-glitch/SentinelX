export const queryKeys = {
  health: ["health"] as const,
  overview: ["overview"] as const,

  authMe: ["auth", "me"] as const,
  users: ["users"] as const,
  userSettings: ["user-settings", "me"] as const,
  deviceCredentials: ["device-credentials"] as const,

  devices: ["devices"] as const,
  device: (deviceId: string) => ["device", deviceId] as const,
  deviceLatestMetrics: (deviceId: string) =>
    ["device", deviceId, "metrics", "latest"] as const,
  deviceMetricHistory: (deviceId: string, limit: number) =>
    ["device", deviceId, "metrics", "history", limit] as const,
  deviceHealth: (deviceId: string) => ["device", deviceId, "health"] as const,
  deviceSummary: (deviceId: string) => ["device", deviceId, "summary"] as const,

  alerts: ["alerts"] as const,
  recoveryActions: ["recovery-actions"] as const,

  auditLogs: ["audit-logs"] as const,
  securityLogs: ["security-logs"] as const,
  incidents: ["incidents"] as const,
  incident: (incidentId: string) => ["incidents", incidentId] as const,
  incidentEvents: (incidentId: string) =>
    ["incidents", incidentId, "events"] as const,
  alertRules: ["alert-rules"] as const,

  anomalyPredictions: ["anomaly-predictions"] as const,
  anomalyPrediction: (predictionId: string) =>
    ["anomaly-predictions", predictionId] as const,
  anomalyModels: ["anomaly-models"] as const,
};