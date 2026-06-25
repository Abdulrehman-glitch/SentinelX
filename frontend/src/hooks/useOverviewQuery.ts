import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useOverviewQuery() {
  return useQuery({
    queryKey: queryKeys.overview,
    queryFn: sentinelxApi.getOverview,
  });
}