import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useSecurityLogsQuery() {
  return useQuery({
    queryKey: queryKeys.securityLogs,
    queryFn: () => sentinelxApi.getSecurityLogs({ limit: 150 }),
  });
}
