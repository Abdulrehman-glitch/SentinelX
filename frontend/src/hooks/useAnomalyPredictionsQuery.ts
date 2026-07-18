import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useAnomalyPredictionsQuery(deviceId?: string) {
  return useQuery({
    queryKey: deviceId ? [...queryKeys.anomalyPredictions, deviceId] : queryKeys.anomalyPredictions,
    queryFn: () => sentinelxApi.getAnomalyPredictions(deviceId ? { device_id: deviceId } : {}),
    refetchInterval: 20_000,
  });
}
