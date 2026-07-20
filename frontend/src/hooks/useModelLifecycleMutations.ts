import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { EvaluateModelPayload, PromoteModelPayload, RetireModelPayload } from "../types/api";

export function useEvaluateModelMutation(modelId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: EvaluateModelPayload) => sentinelxApi.evaluateModel(modelId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.modelEvaluations(modelId) });
    },
  });
}

export function usePromoteModelMutation(modelId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: PromoteModelPayload) => sentinelxApi.promoteModel(modelId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.anomalyModels });
    },
  });
}

export function useRetireModelMutation(modelId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: RetireModelPayload) => sentinelxApi.retireModel(modelId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.anomalyModels });
    },
  });
}
