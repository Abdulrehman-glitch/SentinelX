import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useAnomalyPredictionQuery(predictionId: string) {
  return useQuery({
    queryKey: queryKeys.anomalyPrediction(predictionId),
    queryFn: () => sentinelxApi.getAnomalyPrediction(predictionId),
    enabled: Boolean(predictionId),
    refetchInterval: 20_000,
  });
}
