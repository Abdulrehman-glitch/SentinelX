import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useHybridDecisionQuery(decisionId: string) {
  return useQuery({
    queryKey: queryKeys.hybridDecision(decisionId),
    queryFn: () => sentinelxApi.getHybridDecision(decisionId),
    enabled: Boolean(decisionId),
  });
}
