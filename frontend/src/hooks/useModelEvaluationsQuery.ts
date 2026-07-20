import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useModelEvaluationsQuery(modelId: string) {
  return useQuery({
    queryKey: queryKeys.modelEvaluations(modelId),
    queryFn: () => sentinelxApi.getModelEvaluations(modelId),
    enabled: Boolean(modelId),
  });
}
