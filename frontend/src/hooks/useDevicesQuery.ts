import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useDevicesQuery() {
  return useQuery({
    queryKey: queryKeys.devices,
    queryFn: sentinelxApi.getDevices,
    refetchInterval: 15_000,
  });
}