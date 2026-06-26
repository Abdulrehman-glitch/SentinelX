import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useDeviceMetricHistoryQuery(deviceId: string, limit = 100) {
  return useQuery({
    queryKey: queryKeys.deviceMetricHistory(deviceId, limit),
    queryFn: () => sentinelxApi.getDeviceMetricHistory(deviceId, limit),
    enabled: Boolean(deviceId),
    refetchInterval: 15_000,
  });
}