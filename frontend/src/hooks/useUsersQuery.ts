import { useQuery } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export function useUsersQuery() {
  return useQuery({
    queryKey: queryKeys.users,
    queryFn: sentinelxApi.getUsers,
  });
}