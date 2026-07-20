import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { ReviewHybridDecisionPayload } from "../types/api";

export function useRunHybridDetectionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { device_id?: string } = {}) => sentinelxApi.runHybridDetection(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.hybridDecisions });
    },
  });
}

export function useReviewHybridDecisionMutation(decisionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: ReviewHybridDecisionPayload) =>
      sentinelxApi.reviewHybridDecision(decisionId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.hybridDecisions }),
        queryClient.invalidateQueries({ queryKey: queryKeys.hybridDecision(decisionId) }),
      ]);
    },
  });
}

export function useProposeRecoveryFromHybridDecisionMutation(decisionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => sentinelxApi.proposeRecoveryFromHybridDecision(decisionId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.recoveryCommands }),
        queryClient.invalidateQueries({ queryKey: queryKeys.hybridDecision(decisionId) }),
      ]);
    },
  });
}
