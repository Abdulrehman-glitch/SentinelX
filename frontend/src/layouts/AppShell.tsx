import {
  Activity,
  AlertTriangle,
  ClipboardList,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Radar,
  ScrollText,
  Settings,
  ShieldCheck,
  Siren,
  UserCog,
  UserRound,
  Bell,
  BrainCircuit,
  FileText,
  Network,
  Command,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { Link, NavLink, Outlet } from "react-router";
import { useAuth } from "../contexts/AuthContext";
import type { UserRole } from "../types/api";
import { BarChart3, PlugZap } from "lucide-react";

type NavItem = {
  label: string;

  to: string;
  icon: LucideIcon;
  end?: boolean;
  roles?: UserRole[];
};

const navItems: NavItem[] = [
  { label: "Command", to: "/", icon: LayoutDashboard, end: true },
  { label: "Devices", to: "/devices", icon: Activity },
  { label: "Metrics", to: "/metrics", icon: BarChart3 },
  { label: "Topology", to: "/topology", icon: Network },
  { label: "Anomalies", to: "/anomalies", icon: BrainCircuit },
  { label: "Alerts", to: "/alerts", icon: AlertTriangle },
  { label: "Notifications", to: "/notifications", icon: Bell },
  { label: "Recovery", to: "/recovery-actions", icon: Wrench },
  { label: "Recovery Cmd", to: "/recovery-command", icon: Command },
  { label: "Incidents", to: "/incidents", icon: ClipboardList },
  { label: "Rules", to: "/alert-rules", icon: Siren, roles: ["admin"] },
  { label: "Audit", to: "/audit-logs", icon: ScrollText, roles: ["admin"] },
  { label: "Users", to: "/users", icon: UserCog, roles: ["admin"] },
  {
    label: "Credentials",
    to: "/device-credentials",
    icon: KeyRound,
    roles: ["admin"],
  },
  { label: "Agent Setup", to: "/agent-setup", icon: PlugZap, roles: ["admin"] },

  { label: "Settings", to: "/settings", icon: Settings },
];

function canSeeItem(userRole: UserRole | undefined, item: NavItem) {
  if (!item.roles) {
    return true;
  }

  if (!userRole) {
    return false;
  }

  return item.roles.includes(userRole);
}

function getNavLinkClass({ isActive }: { isActive: boolean }) {
  return [
    "group flex items-center gap-3 border-l-2 px-3 py-2.5 text-sm font-semibold transition",
    isActive
      ? "border-amber-400 bg-amber-400/8 text-amber-200"
      : "border-transparent text-slate-400 hover:border-amber-400/40 hover:bg-white/[0.03] hover:text-slate-100",
  ].join(" ");
}

function NavIcon({ icon: Icon }: { icon: LucideIcon }) {
  return <Icon size={17} strokeWidth={1.8} />;
}

export function AppShell() {
  const { user, logout } = useAuth();

  const visibleItems = navItems.filter((item) => canSeeItem(user?.role, item));

  return (
    <div className="sentinelx-console min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-[220px] overflow-y-auto border-r border-white/[0.056] bg-[#07080d] px-3 py-5 lg:block">
        <div className="px-3">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-amber-400 text-sm font-black text-black">
              SX
            </div>

            <div>
              <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.24em] text-amber-400">
                SentinelX
              </p>
              <p className="text-sm font-bold text-slate-100">Forge Console</p>
            </div>
          </div>
        </div>

        <nav className="mt-7 space-y-1">
          {visibleItems.map((item) => (
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

        <div className="mt-8 border-t border-white/[0.056] px-3 pt-5">
          <Link
            to="/profile"
            className="flex items-center gap-3 rounded-xl px-2 py-2 transition hover:bg-white/[0.03]"
          >
            <div className="flex size-9 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-amber-400">
              <UserRound size={17} />
            </div>

            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-100">
                {user?.full_name ?? "User"}
              </p>
              <p className="font-mono text-[11px] text-slate-500">
                {user?.role ?? "unknown"}
              </p>
            </div>
          </Link>

          <button
            type="button"
            onClick={logout}
            className="mt-3 flex w-full items-center gap-3 rounded-xl px-2 py-2 text-sm font-semibold text-slate-400 transition hover:bg-white/[0.03] hover:text-rose-300"
          >
            <LogOut size={17} />
            Logout
          </button>
        </div>

        <div className="mt-6 px-3">
          <div className="flex items-center gap-2 rounded-xl border border-white/[0.056] px-3 py-2">
            <span className="size-2 rounded-full bg-green-500" />
            <p className="font-mono text-[11px] text-slate-400">
              Live / FastAPI + PostgreSQL
            </p>
          </div>
        </div>
      </aside>

      <div className="lg:pl-[220px]">
        <header className="sticky top-0 z-10 border-b border-white/[0.056] bg-[#07080d]/95 px-5 py-4 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-amber-400 text-sm font-black text-black">
                SX
              </div>

              <div>
                <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.24em] text-amber-400">
                  SentinelX
                </p>
                <p className="text-sm font-bold text-slate-100">
                  Forge Console
                </p>
              </div>
            </div>

            <ShieldCheck size={20} className="text-amber-400" />
          </div>

          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1">
            {visibleItems.map((item) => {
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className="flex shrink-0 items-center gap-2 rounded-lg border border-white/[0.056] px-3 py-2 text-xs font-semibold text-slate-300"
                >
                  <Icon size={15} />
                  {item.label}
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
