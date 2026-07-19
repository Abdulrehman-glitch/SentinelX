import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useRecoveryCommandsQuery(deviceId?: string) {
  return useQuery({
    queryKey: deviceId ? [...queryKeys.recoveryCommands, deviceId] : queryKeys.recoveryCommands,
    queryFn: () => sentinelxApi.getRecoveryCommands(deviceId ? { device_id: deviceId } : {}),
    refetchInterval: 20_000,
  });
}
