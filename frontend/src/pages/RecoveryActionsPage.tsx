import { RecoveryActionsTable } from "../components/RecoveryActionsTable";
import { useRecoveryActionsQuery } from "../hooks/useRecoveryActionsQuery";

export function RecoveryActionsPage() {
  const recoveryActionsQuery = useRecoveryActionsQuery();

  const errorMessage =
    recoveryActionsQuery.error instanceof Error
      ? recoveryActionsQuery.error.message
      : recoveryActionsQuery.error
        ? "Unknown error while loading recovery actions."
        : null;

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
              Recovery
            </p>

            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
              Recovery Actions
            </h1>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              Logged non-destructive recovery actions used to demonstrate safe
              self-healing behaviour and operational traceability.
            </p>
          </div>

          <button
            type="button"
            onClick={() => recoveryActionsQuery.refetch()}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={recoveryActionsQuery.isFetching}
          >
            {recoveryActionsQuery.isFetching ? "Refreshing..." : "Refresh actions"}
          </button>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <p className="font-semibold">Could not load recovery actions.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <RecoveryActionsTable
          recoveryActions={recoveryActionsQuery.data ?? []}
        />

        <p className="mt-4 text-xs text-slate-500">
          Cache: TanStack Query enabled
        </p>
      </section>
    </main>
  );
}