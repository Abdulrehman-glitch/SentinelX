import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useRecoveryCommandEventsQuery(commandId: string) {
  return useQuery({
    queryKey: queryKeys.recoveryCommandEvents(commandId),
    queryFn: () => sentinelxApi.getRecoveryCommandEvents(commandId),
    enabled: Boolean(commandId),
    refetchInterval: 15_000,
  });
}
