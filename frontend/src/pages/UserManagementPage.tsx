import { RefreshCw, UserPlus } from "lucide-react";
import { useState } from "react";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { CreateUserForm } from "../components/CreateUserForm";
import { UserManagementTable } from "../components/UserManagementTable";
import { useUsersQuery } from "../hooks/useUsersQuery";

export function UserManagementPage() {
  const usersQuery = useUsersQuery();
  const [showAddUser, setShowAddUser] = useState(false);

  const errorMessage =
    usersQuery.error instanceof Error
      ? usersQuery.error.message
      : usersQuery.error
        ? "Unknown error while loading users."
        : null;

  const users = usersQuery.data ?? [];
  const activeCount = users.filter((u) => u.is_active).length;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Access Control"
          title="Users & Roles"
          description="Manage organization members and their role-based access to SentinelX."
        >
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => usersQuery.refetch()}
              className="sx-button-secondary"
              disabled={usersQuery.isFetching}
            >
              <RefreshCw size={15} className={usersQuery.isFetching ? "animate-spin" : ""} />
              {usersQuery.isFetching ? "Refreshing…" : "Refresh"}
            </button>
            <button
              type="button"
              onClick={() => setShowAddUser((v) => !v)}
              className="sx-button-primary"
            >
              <UserPlus size={16} />
              Add user
            </button>
          </div>
        </ConsoleHeader>

        {/* Summary chips */}
        {!errorMessage && (
          <div className="mb-6 flex flex-wrap gap-3">
            <div className="sx-stat-card" style={{ minWidth: 150 }}>
              <span className="sx-stat-label">Total users</span>
              <span className="sx-stat-value">{users.length}</span>
            </div>
            <div className="sx-stat-card" style={{ minWidth: 150 }}>
              <span className="sx-stat-label">Active</span>
              <span className="sx-stat-value" style={{ color: "var(--sx-green)" }}>{activeCount}</span>
            </div>
            <div className="sx-stat-card" style={{ minWidth: 150 }}>
              <span className="sx-stat-label">Inactive</span>
              <span className="sx-stat-value" style={{ color: "var(--sx-muted)" }}>{users.length - activeCount}</span>
            </div>
          </div>
        )}

        {showAddUser && <CreateUserForm onClose={() => setShowAddUser(false)} />}

        {errorMessage && (
          <div
            className="mb-6 rounded-2xl p-4 text-sm"
            style={{ background: "rgba(225,29,72,0.07)", border: "1px solid rgba(225,29,72,0.22)", color: "var(--sx-red)" }}
          >
            <p className="font-semibold">Could not load users.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <UserManagementTable users={users} />
      </section>
    </main>
  );
}
