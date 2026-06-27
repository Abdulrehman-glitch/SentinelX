import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useAlertRulesQuery() {
  return useQuery({
    queryKey: queryKeys.alertRules,
    queryFn: sentinelxApi.getAlertRules,
  });
}