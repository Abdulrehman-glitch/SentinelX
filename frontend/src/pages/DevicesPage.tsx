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
    <main className="min-h-screen bg-slate-50">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
              Devices
            </p>

            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              Registered Devices
            </h1>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              Machines and agents currently registered with the SentinelX
              monitoring backend.
            </p>
          </div>

          <button
            type="button"
            onClick={() => devicesQuery.refetch()}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={devicesQuery.isFetching}
          >
            {devicesQuery.isFetching ? "Refreshing..." : "Refresh devices"}
          </button>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
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