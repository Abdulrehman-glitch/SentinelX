import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useDeviceHealthQuery(deviceId: string) {
  return useQuery({
    queryKey: queryKeys.deviceHealth(deviceId),
    queryFn: () => sentinelxApi.getDeviceHealth(deviceId),
    enabled: Boolean(deviceId),
    refetchInterval: 10_000,
  });
}