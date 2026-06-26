import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useDeviceQuery(deviceId: string) {
  return useQuery({
    queryKey: queryKeys.device(deviceId),
    queryFn: () => sentinelxApi.getDevice(deviceId),
    enabled: Boolean(deviceId),
  });
}