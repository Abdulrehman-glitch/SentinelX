import { useEffect, useState } from "react";
import { sentinelxApi } from "../lib/api";
import type {
  Alert,
  Device,
  HealthResponse,
  OverviewResponse,
  RecoveryAction,
} from "../types/api";

export function useSentinelXData() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [recoveryActions, setRecoveryActions] = useState<RecoveryAction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [resolvingAlertId, setResolvingAlertId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function loadDashboardData() {
    try {
      setIsLoading(true);
      setErrorMessage(null);

      const [
        overviewResponse,
        healthResponse,
        devicesResponse,
        alertsResponse,
        recoveryActionsResponse,
      ] = await Promise.all([
        sentinelxApi.getOverview(),
        sentinelxApi.getHealth(),
        sentinelxApi.getDevices(),
        sentinelxApi.getAlerts(),
        sentinelxApi.getRecoveryActions(),
      ]);

      setOverview(overviewResponse);
      setHealth(healthResponse);
      setDevices(devicesResponse);
      setAlerts(alertsResponse);
      setRecoveryActions(recoveryActionsResponse);
      setLastUpdated(new Date());
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unknown error while loading SentinelX dashboard data.";

      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  }

  async function resolveAlert(alertId: string) {
    if (!alertId) {
      return;
    }

    try {
      setResolvingAlertId(alertId);
      setErrorMessage(null);

      await sentinelxApi.resolveAlert(alertId);
      await loadDashboardData();
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unknown error while resolving the alert.";

      setErrorMessage(message);
    } finally {
      setResolvingAlertId(null);
    }
  }

  useEffect(() => {
    loadDashboardData();
  }, []);

  return {
    overview,
    health,
    devices,
    alerts,
    recoveryActions,
    isLoading,
    resolvingAlertId,
    errorMessage,
    lastUpdated,
    loadDashboardData,
    resolveAlert,
  };
}