import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useDeviceLatestMetricsQuery(deviceId: string) {
  return useQuery({
    queryKey: queryKeys.deviceLatestMetrics(deviceId),
    queryFn: () => sentinelxApi.getDeviceLatestMetrics(deviceId),
    enabled: Boolean(deviceId),
    refetchInterval: 10_000,
  });
}