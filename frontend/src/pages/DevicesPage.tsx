import { Monitor } from "lucide-react";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { DevicesTable } from "../components/DevicesTable";
import { PageSkeleton, Skeleton } from "../components/SkeletonPanel";
import { useDevicesQuery } from "../hooks/useDevicesQuery";

export function DevicesPage() {
  const devicesQuery = useDevicesQuery();

  const errorMessage =
    devicesQuery.error instanceof Error
      ? devicesQuery.error.message
      : devicesQuery.error
        ? "Unknown error while loading devices."
        : null;

  const onlineCount  = (devicesQuery.data ?? []).filter((d) => d.status?.toLowerCase() === "online").length;
  const totalCount   = devicesQuery.data?.length ?? 0;
  const offlineCount = totalCount - onlineCount;

  return (
    <main className="min-h-screen" style={{ background: "var(--sx-bg)" }}>
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Device Registry"
          title="Monitored Assets"
          description="Machines and agents currently registered with the SentinelX monitoring backend."
        >
          <button
            type="button"
            onClick={() => devicesQuery.refetch()}
            className="sx-button-primary"
            disabled={devicesQuery.isFetching}
          >
            {devicesQuery.isFetching ? "Refreshing…" : "Refresh devices"}
          </button>
        </ConsoleHeader>

        <Skeleton
          name="devices-page"
          loading={devicesQuery.isLoading}
          animate="shimmer"
          transition={200}
          stagger={50}
          fallback={<PageSkeleton rows={5} cols={4} showStats />}
        >
          {/* Fleet summary */}
          {totalCount > 0 && (
            <div className="mb-6 grid gap-3 sm:grid-cols-3 sx-animate-in sx-delay-2">
              <StatCard icon={<Monitor size={14} strokeWidth={1.8} />} label="Total devices" value={totalCount} />
              <StatCard
                dot="var(--sx-green)"
                label="Online"
                value={onlineCount}
                valueColor="var(--sx-green)"
              />
              <StatCard
                dot="var(--sx-red)"
                label="Offline"
                value={offlineCount}
                valueColor={offlineCount > 0 ? "var(--sx-red)" : undefined}
              />
            </div>
          )}

          {errorMessage && <ErrorBanner message={errorMessage} />}

          <DevicesTable devices={devicesQuery.data ?? []} />
        </Skeleton>
      </section>
    </main>
  );
}

function StatCard({
  icon,
  dot,
  label,
  value,
  valueColor,
}: {
  icon?: React.ReactNode;
  dot?: string;
  label: string;
  value: number;
  valueColor?: string;
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{ background: "var(--sx-panel)", borderColor: "var(--sx-border)" }}
    >
      {icon && <span style={{ color: "var(--sx-muted)" }}>{icon}</span>}
      {dot && (
        <span
          className="sx-live-dot shrink-0"
          style={{ color: dot }}
        />
      )}
      <div>
        <p className="text-xs" style={{ color: "var(--sx-muted)" }}>{label}</p>
        <p
          className="text-sm font-bold"
          style={{ color: valueColor ?? "var(--sx-text)" }}
        >
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
      <p className="font-semibold">Could not load devices.</p>
      <p className="mt-1" style={{ color: "var(--sx-red)" }}>{message}</p>
    </div>
  );
}
