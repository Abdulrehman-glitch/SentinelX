import { useMutation } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import type { ReplayRunPayload } from "../types/api";

export function useReplayMutation() {
  return useMutation({
    mutationFn: (payload: ReplayRunPayload) => sentinelxApi.runReplay(payload),
  });
}
