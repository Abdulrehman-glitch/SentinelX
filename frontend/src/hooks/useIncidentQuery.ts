import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useIncidentQuery(incidentId: string) {
  return useQuery({
    queryKey: queryKeys.incident(incidentId),
    queryFn: () => sentinelxApi.getIncident(incidentId),
    enabled: Boolean(incidentId),
    refetchInterval: 20_000,
  });
}