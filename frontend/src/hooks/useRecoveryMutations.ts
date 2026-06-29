import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { CreateRecoveryActionPayload } from "../types/api";

export function useCreateRecoveryActionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateRecoveryActionPayload) =>
      sentinelxApi.createRecoveryAction(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.recoveryActions }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}