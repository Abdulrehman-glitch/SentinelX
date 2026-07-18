import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { ReviewAnomalyPredictionPayload } from "../types/api";

export function useRunObservabilityPipelineMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { device_id?: string } = {}) => sentinelxApi.runObservabilityPipeline(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.anomalyPredictions });
    },
  });
}

export function useReviewAnomalyPredictionMutation(predictionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: ReviewAnomalyPredictionPayload) =>
      sentinelxApi.reviewAnomalyPrediction(predictionId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.anomalyPredictions }),
        queryClient.invalidateQueries({ queryKey: queryKeys.anomalyPrediction(predictionId) }),
      ]);
    },
  });
}
