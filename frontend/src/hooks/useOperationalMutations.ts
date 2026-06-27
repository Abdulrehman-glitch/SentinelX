import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type {
  CreateAlertRulePayload,
  CreateIncidentEventPayload,
  CreateIncidentPayload,
  UpdateAlertRulePayload,
} from "../types/api";

export function useCreateIncidentMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateIncidentPayload) =>
      sentinelxApi.createIncident(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.incidents }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}

export function useUpdateIncidentStatusMutation(incidentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (status: string) =>
      sentinelxApi.updateIncidentStatus(incidentId, status),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.incidents }),
        queryClient.invalidateQueries({ queryKey: queryKeys.incident(incidentId) }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.incidentEvents(incidentId),
        }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}

export function useResolveIncidentMutation(incidentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => sentinelxApi.resolveIncident(incidentId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.incidents }),
        queryClient.invalidateQueries({ queryKey: queryKeys.incident(incidentId) }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.incidentEvents(incidentId),
        }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}

export function useCreateIncidentEventMutation(incidentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateIncidentEventPayload) =>
      sentinelxApi.createIncidentEvent(incidentId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.incidentEvents(incidentId),
        }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
      ]);
    },
  });
}

export function useCreateAlertRuleMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateAlertRulePayload) =>
      sentinelxApi.createAlertRule(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.alertRules }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}

export function useToggleAlertRuleMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ruleId: string) => sentinelxApi.toggleAlertRule(ruleId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.alertRules }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}

export function useUpdateAlertRuleMutation(ruleId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateAlertRulePayload) =>
      sentinelxApi.updateAlertRule(ruleId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.alertRules }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}