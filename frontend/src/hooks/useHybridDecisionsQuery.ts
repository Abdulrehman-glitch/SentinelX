import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useHybridDecisionsQuery(deviceId?: string) {
  return useQuery({
    queryKey: deviceId ? [...queryKeys.hybridDecisions, deviceId] : queryKeys.hybridDecisions,
    queryFn: () => sentinelxApi.getHybridDecisions(deviceId ? { device_id: deviceId } : {}),
    refetchInterval: 20_000,
  });
}
