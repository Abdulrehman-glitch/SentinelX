import { ConsoleHeader } from "../components/ConsoleHeader";
import { useAuth } from "../contexts/AuthContext";
import { formatDate } from "../utils/format";

export function ProfilePage() {
  const { user, logout } = useAuth();

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Profile"
          title="Account Session"
          description="Current authenticated SentinelX user and session details."
        >
          <button
            type="button"
            onClick={logout}
            className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
          >
            Logout
          </button>
        </ConsoleHeader>

        <section className="sx-panel rounded-2xl p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm font-semibold sx-c-muted">Name</p>
              <p className="mt-2 text-lg font-bold sx-c-text">
                {user?.full_name ?? "Unknown"}
              </p>
            </div>

            <div>
              <p className="text-sm font-semibold sx-c-muted">Email</p>
              <p className="mt-2 text-lg font-bold sx-c-text">
                {user?.email ?? "Unknown"}
              </p>
            </div>

            <div>
              <p className="text-sm font-semibold sx-c-muted">Role</p>
              <p className="mt-2 text-lg font-bold sx-c-text">
                {user?.role ?? "Unknown"}
              </p>
            </div>

            <div>
              <p className="text-sm font-semibold sx-c-muted">Last Login</p>
              <p className="mt-2 text-lg font-bold sx-c-text">
                {formatDate(user?.last_login_at)}
              </p>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}