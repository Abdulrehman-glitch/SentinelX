import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useResolveAlertMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: sentinelxApi.resolveAlert,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.alerts }),
        queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
      ]);
    },
  });
}