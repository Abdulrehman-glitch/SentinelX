import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useUserSettingsQuery() {
  return useQuery({
    queryKey: queryKeys.userSettings,
    queryFn: sentinelxApi.getMySettings,
  });
}