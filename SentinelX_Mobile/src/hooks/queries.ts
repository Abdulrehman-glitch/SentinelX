import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { sentinelxApi } from "@/api/endpoints";

// Query key constants — mirrors the web app's queryKeys.ts convention.
export const queryKeys = {
  overview: ["overview"] as const,
  devices: ["devices"] as const,
  device: (id: string) => ["devices", id] as const,
  deviceSummary: (id: string) => ["devices", id, "summary"] as const,
  alerts: (unresolvedOnly: boolean) => ["alerts", { unresolvedOnly }] as const,
  incidents: (status?: string) => ["incidents", { status }] as const,
  incident: (id: string) => ["incidents", id] as const,
  auditLogs: ["auditLogs"] as const,
  recoveryActions: ["recoveryActions"] as const,
  organization: ["organization"] as const,
};

const STALE_MS = 30_000;

export function useOverviewQuery() {
  return useQuery({ queryKey: queryKeys.overview, queryFn: sentinelxApi.overview, staleTime: STALE_MS });
}

export function useDevicesQuery() {
  return useQuery({ queryKey: queryKeys.devices, queryFn: sentinelxApi.devices, staleTime: STALE_MS });
}

export function useDeviceSummaryQuery(id: string) {
  return useQuery({
    queryKey: queryKeys.deviceSummary(id),
    queryFn: () => sentinelxApi.deviceSummary(id),
    staleTime: 15_000,
    enabled: !!id,
  });
}

export function useAlertsQuery(unresolvedOnly: boolean) {
  return useQuery({
    queryKey: queryKeys.alerts(unresolvedOnly),
    queryFn: () => sentinelxApi.alerts({ unresolvedOnly, limit: 200 }),
    staleTime: STALE_MS,
  });
}

export function useIncidentsQuery(status?: string) {
  return useQuery({
    queryKey: queryKeys.incidents(status),
    queryFn: () => sentinelxApi.incidents({ status, limit: 200 }),
    staleTime: STALE_MS,
  });
}

export function useIncidentQuery(id: string) {
  return useQuery({
    queryKey: queryKeys.incident(id),
    queryFn: () => sentinelxApi.incident(id),
    staleTime: 15_000,
    enabled: !!id,
  });
}

export function useAuditLogsQuery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.auditLogs,
    queryFn: () => sentinelxApi.auditLogs(200),
    staleTime: STALE_MS,
    enabled,
  });
}

export function useOrganizationQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.organization,
    queryFn: sentinelxApi.myOrganization,
    staleTime: 10 * 60_000,
    enabled,
  });
}

export function useResolveAlertMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => sentinelxApi.resolveAlert(alertId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["alerts"] });
      client.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

export function useIncidentStatusMutation(incidentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (status: "open" | "investigating" | "resolved") =>
      status === "resolved"
        ? sentinelxApi.resolveIncident(incidentId)
        : sentinelxApi.updateIncidentStatus(incidentId, status),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["incidents"] });
      client.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

export function useAddIncidentNoteMutation(incidentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (message: string) =>
      sentinelxApi.addIncidentEvent(incidentId, { event_type: "note", message, actor_type: "user" }),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.incident(incidentId) }),
  });
}

export function useCreateIncidentMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: { title: string; description?: string; severity?: "info" | "warning" | "critical"; device_id?: string | null }) =>
      sentinelxApi.createIncident(payload),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["incidents"] });
      client.invalidateQueries({ queryKey: queryKeys.overview });
    },
  });
}

export function useRecoveryRequestMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: { device_id: string; action_type: string; details?: string }) =>
      sentinelxApi.createRecoveryAction({ ...payload, status: "requested" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.recoveryActions });
      client.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}
