import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useIncidentsQuery() {
  return useQuery({
    queryKey: queryKeys.incidents,
    queryFn: sentinelxApi.getIncidents,
    refetchInterval: 20_000,
  });
}