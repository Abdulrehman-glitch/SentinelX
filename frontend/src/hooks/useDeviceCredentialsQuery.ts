import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useDeviceCredentialsQuery() {
  return useQuery({
    queryKey: queryKeys.deviceCredentials,
    queryFn: sentinelxApi.getDeviceCredentials,
  });
}