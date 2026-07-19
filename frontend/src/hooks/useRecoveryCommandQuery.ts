import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useRecoveryCommandQuery(commandId: string) {
  return useQuery({
    queryKey: queryKeys.recoveryCommand(commandId),
    queryFn: () => sentinelxApi.getRecoveryCommand(commandId),
    enabled: Boolean(commandId),
    refetchInterval: 20_000,
  });
}
