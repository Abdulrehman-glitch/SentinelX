import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useRecoveryActionsQuery() {
  return useQuery({
    queryKey: queryKeys.recoveryActions,
    queryFn: sentinelxApi.getRecoveryActions,
  });
}