import { ConsoleHeader } from "../components/ConsoleHeader";
import { CreateDeviceCredentialForm } from "../components/CreateDeviceCredentialForm";
import { DeviceCredentialsTable } from "../components/DeviceCredentialsTable";
import { useDeviceCredentialsQuery } from "../hooks/useDeviceCredentialsQuery";

export function DeviceCredentialsPage() {
  const credentialsQuery = useDeviceCredentialsQuery();

  const errorMessage =
    credentialsQuery.error instanceof Error
      ? credentialsQuery.error.message
      : credentialsQuery.error
        ? "Unknown error while loading device credentials."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Agent Security"
          title="Device Credentials"
          description="Create and revoke API credentials used by SentinelX agents and monitored devices."
        >
          <button
            type="button"
            onClick={() => credentialsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
          >
            Refresh credentials
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Could not load credentials.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <CreateDeviceCredentialForm />
        <DeviceCredentialsTable credentials={credentialsQuery.data ?? []} />
      </section>
    </main>
  );
}