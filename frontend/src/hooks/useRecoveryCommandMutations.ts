import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CreateRecoveryCommandPayload, ProposeRecoveryFromAnomalyPayload } from "../types/api";

function useInvalidateCommand(commandId: string) {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.recoveryCommands }),
      queryClient.invalidateQueries({ queryKey: queryKeys.recoveryCommand(commandId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.recoveryCommandEvents(commandId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
      queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
    ]);
  };
}

export function useCreateRecoveryCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateRecoveryCommandPayload) => sentinelxApi.createRecoveryCommand(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.recoveryCommands }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
      ]);
    },
  });
}

export function useProposeRecoveryFromAnomalyMutation(predictionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProposeRecoveryFromAnomalyPayload) =>
      sentinelxApi.proposeRecoveryFromAnomaly(predictionId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.recoveryCommands }),
        queryClient.invalidateQueries({ queryKey: queryKeys.anomalyPrediction(predictionId) }),
      ]);
    },
  });
}

export function useApproveRecoveryCommandMutation(commandId: string) {
  const invalidate = useInvalidateCommand(commandId);
  return useMutation({
    mutationFn: () => sentinelxApi.approveRecoveryCommand(commandId),
    onSuccess: invalidate,
  });
}

export function useRejectRecoveryCommandMutation(commandId: string) {
  const invalidate = useInvalidateCommand(commandId);
  return useMutation({
    mutationFn: (reason: string) => sentinelxApi.rejectRecoveryCommand(commandId, reason),
    onSuccess: invalidate,
  });
}

export function useCancelRecoveryCommandMutation(commandId: string) {
  const invalidate = useInvalidateCommand(commandId);
  return useMutation({
    mutationFn: () => sentinelxApi.cancelRecoveryCommand(commandId),
    onSuccess: invalidate,
  });
}

export function useRetryRecoveryCommandMutation(commandId: string) {
  const invalidate = useInvalidateCommand(commandId);
  return useMutation({
    mutationFn: () => sentinelxApi.retryRecoveryCommand(commandId),
    onSuccess: invalidate,
  });
}
