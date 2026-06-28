import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type {
  CreateDeviceCredentialPayload,
  UpdateUserRolePayload,
  UpdateUserSettingsPayload,
} from "../types/api";

export function useUpdateUserRoleMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UpdateUserRolePayload["role"] }) =>
      sentinelxApi.updateUserRole(userId, { role }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.users }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
      ]);
    },
  });
}

export function useDeactivateUserMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: sentinelxApi.deactivateUser,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.users }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
      ]);
    },
  });
}

export function useUpdateUserSettingsMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateUserSettingsPayload) =>
      sentinelxApi.updateMySettings(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.userSettings });
    },
  });
}

export function useCreateDeviceCredentialMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateDeviceCredentialPayload) =>
      sentinelxApi.createDeviceCredential(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.deviceCredentials }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
      ]);
    },
  });
}

export function useRevokeDeviceCredentialMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: sentinelxApi.revokeDeviceCredential,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.deviceCredentials }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auditLogs }),
      ]);
    },
  });
}