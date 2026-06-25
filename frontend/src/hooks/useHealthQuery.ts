import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useHealthQuery() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: sentinelxApi.getHealth,
  });
}