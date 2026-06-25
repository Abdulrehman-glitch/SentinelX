import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useAlertsQuery() {
  return useQuery({
    queryKey: queryKeys.alerts,
    queryFn: sentinelxApi.getAlerts,
  });
}