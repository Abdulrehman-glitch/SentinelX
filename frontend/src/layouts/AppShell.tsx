import { NavLink, Outlet } from "react-router";

type NavItem = {
  label: string;
  to: string;
  end?: boolean;
};

const primaryNavItems: NavItem[] = [
  { label: "Dashboard", to: "/", end: true },
  { label: "Devices", to: "/devices" },
  { label: "Alerts", to: "/alerts" },
  { label: "Recovery Actions", to: "/recovery-actions" },
];

const plannedNavItems = [
  "Metrics",
  "Alert Rules",
  "Incidents",
  "Audit Logs",
  "Users & Roles",
  "Settings",
];

function getNavLinkClass({ isActive }: { isActive: boolean }) {
  return [
    "block rounded-xl px-3 py-2 text-sm font-medium transition",
    isActive
      ? "bg-slate-950 text-white shadow-sm"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
  ].join(" ");
}

export function AppShell() {
  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-slate-200 bg-white px-5 py-6 lg:block">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
            SentinelX
          </p>

          <h1 className="mt-2 text-xl font-bold tracking-tight text-slate-950">
            Operations Console
          </h1>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            Distributed monitoring, alerting, and recovery visibility.
          </p>
        </div>

        <nav className="mt-8 space-y-1">
          {primaryNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={getNavLinkClass}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-8 border-t border-slate-200 pt-6">
          <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Planned modules
          </p>

          <div className="mt-3 space-y-1">
            {plannedNavItems.map((item) => (
              <div
                key={item}
                className="rounded-xl px-3 py-2 text-sm font-medium text-slate-300"
                title="Planned for a later milestone"
              >
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="absolute bottom-6 left-5 right-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold text-slate-700">
            Development mode
          </p>

          <p className="mt-1 text-xs leading-5 text-slate-500">
            Frontend is connected to the local FastAPI backend.
          </p>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 px-5 py-4 backdrop-blur lg:hidden">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">
            SentinelX
          </p>

          <nav className="mt-3 flex gap-2 overflow-x-auto pb-1">
            {primaryNavItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={getNavLinkClass}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <Outlet />
      </div>
    </div>
  );
}