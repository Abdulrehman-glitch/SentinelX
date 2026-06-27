import {
  Activity,
  AlertTriangle,
  ClipboardList,
  DatabaseZap,
  LayoutDashboard,
  LockKeyhole,
  Radar,
  ScrollText,
  Settings,
  ShieldCheck,
  Siren,
  TerminalSquare,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { ShellBadge } from "../components/ShellBadge";

type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  end?: boolean;
};

type PlannedItem = {
  label: string;
  icon: LucideIcon;
};

const primaryNavItems: NavItem[] = [
  { label: "Command Center", to: "/", icon: LayoutDashboard, end: true },
  { label: "Devices", to: "/devices", icon: Activity },
  { label: "Alerts", to: "/alerts", icon: AlertTriangle },
  { label: "Recovery", to: "/recovery-actions", icon: Wrench },
  { label: "Incidents", to: "/incidents", icon: ClipboardList },
  { label: "Alert Rules", to: "/alert-rules", icon: Siren },
  { label: "Audit Logs", to: "/audit-logs", icon: ScrollText },
];

const plannedNavItems: PlannedItem[] = [
  { label: "Metrics Explorer", icon: DatabaseZap },
  { label: "Users & Roles", icon: LockKeyhole },
  { label: "Settings", icon: Settings },
];

function getNavLinkClass({ isActive }: { isActive: boolean }) {
  return [
    "group flex items-center gap-3 rounded-2xl px-3 py-3 text-sm font-semibold transition",
    isActive
      ? "border border-cyan-400/30 bg-cyan-400/12 text-cyan-50 shadow-[0_0_28px_rgba(56,189,248,0.12)]"
      : "border border-transparent text-slate-400 hover:border-slate-700/70 hover:bg-slate-800/50 hover:text-slate-100",
  ].join(" ");
}

function NavIcon({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="flex size-9 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-950/70 text-cyan-300 transition group-hover:border-cyan-400/30 group-hover:text-cyan-200">
      <Icon size={18} strokeWidth={1.8} />
    </span>
  );
}

export function AppShell() {
  return (
    <div className="sentinelx-console min-h-screen">
      <aside className="sx-shell-panel fixed inset-y-0 left-0 hidden w-80 overflow-y-auto border-r px-5 py-6 lg:block">
        <div className="flex items-center gap-3">
          <div className="flex size-12 items-center justify-center rounded-2xl border border-cyan-400/30 bg-cyan-400/10 text-cyan-200 shadow-[0_0_30px_rgba(56,189,248,0.16)]">
            <Radar size={25} strokeWidth={1.8} />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-cyan-300/80">
              SentinelX
            </p>

            <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-50">
              Ops Console
            </h1>
          </div>
        </div>

        <div className="mt-6">
          <ShellBadge label="Runtime" value="Local FastAPI + PostgreSQL" />
        </div>

        <nav className="mt-8 space-y-2">
          {primaryNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={getNavLinkClass}
            >
              <NavIcon icon={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-8 border-t border-slate-800 pt-6">
          <p className="px-3 text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
            Future modules
          </p>

          <div className="mt-3 space-y-2">
            {plannedNavItems.map((item) => {
              const Icon = item.icon;

              return (
                <div
                  key={item.label}
                  className="flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-sm font-semibold text-slate-600"
                  title="Planned for a later milestone"
                >
                  <span className="flex size-9 items-center justify-center rounded-xl border border-slate-800 bg-slate-950/50">
                    <Icon size={18} strokeWidth={1.8} />
                  </span>

                  <span>{item.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-8 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="flex items-center gap-2 text-cyan-300">
            <TerminalSquare size={17} strokeWidth={1.8} />
            <p className="text-xs font-semibold uppercase tracking-[0.22em]">
              Build mode
            </p>
          </div>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            Professional monitoring interface. Real backend data only.
          </p>
        </div>
      </aside>

      <div className="lg:pl-80">
        <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/88 px-5 py-4 backdrop-blur lg:hidden">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-2xl border border-cyan-400/30 bg-cyan-400/10 text-cyan-200">
              <ShieldCheck size={21} strokeWidth={1.8} />
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-300/80">
                SentinelX
              </p>
              <p className="text-sm font-bold text-slate-50">Ops Console</p>
            </div>
          </div>

          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1">
            {primaryNavItems.map((item) => {
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={getNavLinkClass}
                >
                  <Icon size={17} strokeWidth={1.8} />
                  <span className="whitespace-nowrap">{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </header>

        <Outlet />
      </div>
    </div>
  );
}