import { AlertsTable } from "../components/AlertsTable";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { PageSkeleton, Skeleton } from "../components/SkeletonPanel";
import { useAlertsQuery } from "../hooks/useAlertsQuery";
import { useResolveAlertMutation } from "../hooks/useResolveAlertMutation";
import {
  getCriticalOpenAlerts,
  getOpenAlerts,
  getWarningOpenAlerts,
} from "../utils/operations";

export function AlertsPage() {
  const alertsQuery         = useAlertsQuery();
  const resolveAlertMutation = useResolveAlertMutation();

  const queryErrorMessage =
    alertsQuery.error instanceof Error
      ? alertsQuery.error.message
      : alertsQuery.error
        ? "Unknown error while loading alerts."
        : null;

  const mutationErrorMessage =
    resolveAlertMutation.error instanceof Error
      ? resolveAlertMutation.error.message
      : resolveAlertMutation.error
        ? "Unknown error while resolving alert."
        : null;

  const errorMessage = queryErrorMessage ?? mutationErrorMessage;

  const alerts  = alertsQuery.data ?? [];
  const open    = getOpenAlerts(alerts);
  const critical = getCriticalOpenAlerts(alerts);
  const warning  = getWarningOpenAlerts(alerts);

  return (
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Alert Operations"
          title="Signal Review"
          description="Warning and critical conditions generated from monitored telemetry. Resolve alerts once reviewed."
        >
          <button
            type="button"
            onClick={() => alertsQuery.refetch()}
            className="sx-button-primary"
            disabled={alertsQuery.isFetching}
          >
            {alertsQuery.isFetching ? "Refreshing…" : "Refresh alerts"}
          </button>
        </ConsoleHeader>

        <Skeleton
          name="alerts-page"
          loading={alertsQuery.isLoading}
          animate="shimmer"
          transition={200}
          stagger={50}
          fallback={<PageSkeleton rows={6} cols={5} showStats />}
        >
          {/* Severity summary */}
          {alerts.length > 0 && (
            <div className="mb-6 grid gap-3 sm:grid-cols-3 sx-animate-in sx-delay-2">
              <SeverityCard label="Open alerts" value={open.length}     />
              <SeverityCard label="Critical"    value={critical.length} dotColor="var(--sx-red)" valueColor="var(--sx-red)" />
              <SeverityCard label="Warning"     value={warning.length}  dotColor="var(--sx-amber)" valueColor="var(--sx-amber)" />
            </div>
          )}

          {errorMessage && <ErrorBanner message={errorMessage} />}

          <AlertsTable
            alerts={alerts}
            resolvingAlertId={
              resolveAlertMutation.isPending &&
              typeof resolveAlertMutation.variables === "string"
                ? resolveAlertMutation.variables
                : null
            }
            onResolveAlert={resolveAlertMutation.mutate}
          />
        </Skeleton>
      </section>
    </main>
  );
}

function SeverityCard({
  label,
  value,
  dotColor,
  valueColor,
}: {
  label: string;
  value: number;
  dotColor?: string;
  valueColor?: string;
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
    >
      {dotColor ? (
        <span
          className="sx-live-dot shrink-0"
          style={{ color: dotColor }}
        />
      ) : (
        <span
          className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ background: "var(--sx-muted)" }}
        />
      )}
      <div>
        <p className="text-xs" style={{ color: "var(--sx-muted)" }}>{label}</p>
        <p className="text-sm font-bold" style={{ color: valueColor ?? "var(--sx-text)" }}>
          {value}
        </p>
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="mb-6 rounded-lg border p-4 text-sm"
      style={{
        borderColor: "rgba(244,63,94,0.24)",
        background: "rgba(244,63,94,0.08)",
        color: "var(--sx-red)",
      }}
    >
      <p className="font-semibold">Alert operation failed.</p>
      <p className="mt-1" style={{ color: "var(--sx-red)" }}>{message}</p>
    </div>
  );
}
