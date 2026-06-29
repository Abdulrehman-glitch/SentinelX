import { ConsoleHeader } from "../components/ConsoleHeader";
import { UserManagementTable } from "../components/UserManagementTable";
import { useUsersQuery } from "../hooks/useUsersQuery";

export function UserManagementPage() {
  const usersQuery = useUsersQuery();

  const errorMessage =
    usersQuery.error instanceof Error
      ? usersQuery.error.message
      : usersQuery.error
        ? "Unknown error while loading users."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Access Control"
          title="Users & Roles"
          description="Admin-only user management for SentinelX role-based access control."
        >
          <button
            type="button"
            onClick={() => usersQuery.refetch()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold"
          >
            Refresh users
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Could not load users.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <UserManagementTable users={usersQuery.data ?? []} />
      </section>
    </main>
  );
}