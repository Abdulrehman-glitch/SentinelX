import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useAuditLogsQuery() {
  return useQuery({
    queryKey: queryKeys.auditLogs,
    queryFn: () => sentinelxApi.getAuditLogs({ limit: 100 }),
    refetchInterval: 20_000,
  });
}