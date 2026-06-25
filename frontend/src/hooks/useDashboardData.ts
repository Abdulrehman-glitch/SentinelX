import { useAlertsQuery } from "./useAlertsQuery";
import { useDevicesQuery } from "./useDevicesQuery";
import { useHealthQuery } from "./useHealthQuery";
import { useOverviewQuery } from "./useOverviewQuery";
import { useRecoveryActionsQuery } from "./useRecoveryActionsQuery";

export function useDashboardData() {
  const overviewQuery = useOverviewQuery();
  const healthQuery = useHealthQuery();
  const devicesQuery = useDevicesQuery();
  const alertsQuery = useAlertsQuery();
  const recoveryActionsQuery = useRecoveryActionsQuery();

  const isLoading =
    overviewQuery.isLoading ||
    healthQuery.isLoading ||
    devicesQuery.isLoading ||
    alertsQuery.isLoading ||
    recoveryActionsQuery.isLoading;

  const isFetching =
    overviewQuery.isFetching ||
    healthQuery.isFetching ||
    devicesQuery.isFetching ||
    alertsQuery.isFetching ||
    recoveryActionsQuery.isFetching;

  const error =
    overviewQuery.error ??
    healthQuery.error ??
    devicesQuery.error ??
    alertsQuery.error ??
    recoveryActionsQuery.error ??
    null;

  async function refetchAll() {
    await Promise.all([
      overviewQuery.refetch(),
      healthQuery.refetch(),
      devicesQuery.refetch(),
      alertsQuery.refetch(),
      recoveryActionsQuery.refetch(),
    ]);
  }

  return {
    overview: overviewQuery.data ?? null,
    health: healthQuery.data ?? null,
    devices: devicesQuery.data ?? [],
    alerts: alertsQuery.data ?? [],
    recoveryActions: recoveryActionsQuery.data ?? [],
    isLoading,
    isFetching,
    error,
    refetchAll,
  };
}