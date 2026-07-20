import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useAnomalyModelsQuery() {
  return useQuery({
    queryKey: queryKeys.anomalyModels,
    queryFn: () => sentinelxApi.getAnomalyModels(),
  });
}
