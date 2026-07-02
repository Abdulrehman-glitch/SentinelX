import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { Badge, getStatusTone } from "../components/Badge";
import { PermissionGate } from "../components/PermissionGate";
import { HealthScorePanel } from "../components/HealthScorePanel";
import { MetricCard } from "../components/MetricCard";
import { MetricHistoryChart } from "../components/MetricHistoryChart";
import { MetricUsageBars } from "../components/MetricUsageBars";
import { MetricsHistoryTable } from "../components/MetricsHistoryTable";
import { useDeviceHealthQuery } from "../hooks/useDeviceHealthQuery";
import { useDeviceLatestMetricsQuery } from "../hooks/useDeviceLatestMetricsQuery";
import { useDeviceMetricHistoryQuery } from "../hooks/useDeviceMetricHistoryQuery";
import { useDeviceQuery } from "../hooks/useDeviceQuery";
import { useDeviceSummaryQuery } from "../hooks/useDeviceSummaryQuery";
import { sentinelxApi } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { formatDate } from "../utils/format";

export function DeviceDetailPage() {
  const params   = useParams();
  const deviceId = params.deviceId ?? "";

  const deviceQuery        = useDeviceQuery(deviceId);
  const latestMetricsQuery = useDeviceLatestMetricsQuery(deviceId);
  const metricHistoryQuery = useDeviceMetricHistoryQuery(deviceId, 100);
  const healthQuery        = useDeviceHealthQuery(deviceId);
  const summaryQuery       = useDeviceSummaryQuery(deviceId);

  const device = summaryQuery.data?.device ?? deviceQuery.data ?? null;
  const latestMetrics =
    summaryQuery.data?.latest_metrics ??
    summaryQuery.data?.latest_metric  ??
    latestMetricsQuery.data           ??
    null;

  const health        = summaryQuery.data?.health ?? healthQuery.data ?? null;
  const metricHistory = metricHistoryQuery.data ?? [];

  const isFetching =
    deviceQuery.isFetching     ||
    latestMetricsQuery.isFetching ||
    metricHistoryQuery.isFetching ||
    healthQuery.isFetching     ||
    summaryQuery.isFetching;

  const error =
    deviceQuery.error        ??
    latestMetricsQuery.error ??
    metricHistoryQuery.error ??
    healthQuery.error        ??
    summaryQuery.error       ??
    null;

  const errorMessage =
    error instanceof Error ? error.message : error ? "Unknown error while loading device details." : null;

  const queryClient = useQueryClient();
  const isDisabled = (device?.status ?? "").toLowerCase() === "disabled";

  const statusMutation = useMutation({
    mutationFn: (enabled: boolean) => sentinelxApi.setDeviceStatus(deviceId, enabled),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.device(deviceId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.deviceSummary(deviceId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.devices }),
      ]);
    },
  });

  async function refreshDeviceData() {
    await Promise.all([
      deviceQuery.refetch(),
      latestMetricsQuery.refetch(),
      metricHistoryQuery.refetch(),
      healthQuery.refetch(),
      summaryQuery.refetch(),
    ]);
  }

  return (
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        {/* Back link */}
        <div className="mb-5 sx-animate-in">
          <Link
            to="/devices"
            className="text-sm font-medium transition-colors hover:text-violet-400"
            style={{ color: "var(--sx-muted)" }}
          >
            ← Back to devices
          </Link>
        </div>

        {/* Device header */}
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between sx-animate-in">
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--sx-accent)", fontFamily: "var(--font-mono)" }}
            >
              Device Detail
            </p>

            <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
              <h1
                className="text-3xl font-bold tracking-tight md:text-4xl"
                style={{ color: "var(--sx-text)" }}
              >
                {device?.hostname ?? "Loading…"}
              </h1>
              <Badge tone={getStatusTone(device?.status ?? "unknown")}>
                {device?.status ?? "unknown"}
              </Badge>
            </div>

            <p className="mt-2 text-sm" style={{ color: "var(--sx-muted)" }}>
              Device ID:{" "}
              <span style={{ color: "var(--sx-text)", fontFamily: "var(--font-mono)" }}>
                {deviceId}
              </span>
            </p>
          </div>

          <div className="flex items-center gap-3">
            <PermissionGate roles={["platform_admin", "owner", "admin", "engineer"]}>
              <button
                type="button"
                onClick={() => statusMutation.mutate(isDisabled)}
                disabled={statusMutation.isPending || !device}
                className="rounded-xl border px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                style={{
                  borderColor: isDisabled ? "rgba(22,163,74,0.4)" : "rgba(225,29,72,0.4)",
                  background: isDisabled ? "rgba(22,163,74,0.08)" : "rgba(225,29,72,0.08)",
                  color: isDisabled ? "var(--sx-green)" : "var(--sx-red)",
                }}
                title={isDisabled ? "Enable this device" : "Disable this device"}
              >
                {statusMutation.isPending
                  ? "Updating…"
                  : isDisabled
                    ? "Enable device"
                    : "Disable device"}
              </button>
            </PermissionGate>

            <button
              type="button"
              onClick={refreshDeviceData}
              className="sx-button-primary"
              disabled={isFetching}
            >
              {isFetching ? "Refreshing…" : "Refresh device"}
            </button>
          </div>
        </header>

        {statusMutation.isError && (
          <div
            className="mb-6 rounded-lg border p-4 text-sm"
            style={{
              borderColor: "rgba(244,63,94,0.24)",
              background: "rgba(244,63,94,0.08)",
              color: "#fb7185",
            }}
          >
            Could not update device status. You may not have permission, or the
            backend is unreachable.
          </div>
        )}

        {errorMessage && (
          <div
            className="mb-6 rounded-lg border p-4 text-sm"
            style={{
              borderColor: "rgba(244,63,94,0.24)",
              background: "rgba(244,63,94,0.08)",
              color: "#fb7185",
            }}
          >
            <p className="font-semibold">Could not load device details.</p>
            <p className="mt-1" style={{ color: "#fca5a5" }}>{errorMessage}</p>
          </div>
        )}

        {/* Info cards */}
        <section className="mb-8 grid gap-4 lg:grid-cols-4 sx-animate-in sx-delay-1">
          {(
            [
              { label: "IP Address",       value: device?.ip_address ?? "Unknown" },
              { label: "Operating System", value: device?.os_name    ?? "Unknown" },
              { label: "Last Seen",        value: formatDate(device?.last_seen ?? device?.updated_at) },
              { label: "Metric Records",   value: String(metricHistory.length) },
            ] as const
          ).map(({ label, value }) => (
            <article
              key={label}
              className="rounded-lg border p-5"
              style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
            >
              <p className="text-xs font-medium" style={{ color: "var(--sx-muted)" }}>{label}</p>
              <p
                className="mt-2 text-xl font-bold"
                style={{ color: "var(--sx-text)", fontFamily: "var(--font-mono)" }}
              >
                {value}
              </p>
            </article>
          ))}
        </section>

        {/* Metric cards */}
        <section className="mb-8 grid gap-4 xl:grid-cols-3 sx-animate-in sx-delay-2">
          <MetricCard title="CPU Usage"    value={latestMetrics?.cpu_percent}    description="Latest processor utilisation reported by the agent." />
          <MetricCard title="Memory Usage" value={latestMetrics?.memory_percent} description="Latest RAM utilisation reported by the agent." />
          <MetricCard title="Disk Usage"   value={latestMetrics?.disk_percent}   description="Latest disk utilisation reported by the agent." />
        </section>

        {/* Health + Chart */}
        <section className="grid gap-6 xl:grid-cols-[400px_1fr]">
          <div className="space-y-6">
            <HealthScorePanel health={health} latestMetrics={latestMetrics} />
            <MetricUsageBars latestMetrics={latestMetrics} />
          </div>
          <MetricHistoryChart metrics={metricHistory} />
        </section>

        <MetricsHistoryTable metrics={metricHistory} />
      </section>
    </main>
  );
}
