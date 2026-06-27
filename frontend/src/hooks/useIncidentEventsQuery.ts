import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useIncidentEventsQuery(incidentId: string) {
  return useQuery({
    queryKey: queryKeys.incidentEvents(incidentId),
    queryFn: () => sentinelxApi.getIncidentEvents(incidentId),
    enabled: Boolean(incidentId),
    refetchInterval: 15_000,
  });
}