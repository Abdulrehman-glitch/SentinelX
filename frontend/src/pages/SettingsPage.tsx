import { ConsoleHeader } from "../components/ConsoleHeader";
import { UserSettingsForm } from "../components/UserSettingsForm";
import { useUserSettingsQuery } from "../hooks/useUserSettingsQuery";

export function SettingsPage() {
  const settingsQuery = useUserSettingsQuery();

  const errorMessage =
    settingsQuery.error instanceof Error
      ? settingsQuery.error.message
      : settingsQuery.error
        ? "Unknown error while loading settings."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Settings"
          title="Accessibility & Preferences"
          description="Control your monitoring interface preferences, accessibility options, and refresh behaviour."
        >
          <button
            type="button"
            onClick={() => settingsQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
          >
            Refresh settings
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Could not load settings.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <UserSettingsForm settings={settingsQuery.data ?? null} />
      </section>
    </main>
  );
}