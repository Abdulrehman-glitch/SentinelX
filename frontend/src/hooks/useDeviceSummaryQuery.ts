import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useDeviceSummaryQuery(deviceId: string) {
  return useQuery({
    queryKey: queryKeys.deviceSummary(deviceId),
    queryFn: () => sentinelxApi.getDeviceSummary(deviceId),
    enabled: Boolean(deviceId),
    refetchInterval: 15_000,
  });
}