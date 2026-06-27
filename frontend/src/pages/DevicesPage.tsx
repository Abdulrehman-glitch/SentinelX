import { ConsoleHeader } from "../components/ConsoleHeader";
import { DevicesTable } from "../components/DevicesTable";
import { useDevicesQuery } from "../hooks/useDevicesQuery";

export function DevicesPage() {
  const devicesQuery = useDevicesQuery();

  const errorMessage =
    devicesQuery.error instanceof Error
      ? devicesQuery.error.message
      : devicesQuery.error
        ? "Unknown error while loading devices."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Device Registry"
          title="Monitored Assets"
          description="Machines and agents currently registered with the SentinelX monitoring backend."
        >
          <button
            type="button"
            onClick={() => devicesQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
            disabled={devicesQuery.isFetching}
          >
            {devicesQuery.isFetching ? "Refreshing..." : "Refresh devices"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Could not load devices.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <DevicesTable devices={devicesQuery.data ?? []} />

        <p className="mt-4 text-xs text-slate-500">
          Cache: TanStack Query enabled
        </p>
      </section>
    </main>
  );
}