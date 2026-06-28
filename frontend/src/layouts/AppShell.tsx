import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ClipboardList,
  LayoutDashboard,
  ScrollText,
  Siren,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router";

type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  end?: boolean;
};

const primaryNavItems: NavItem[] = [
  { label: "Dashboard",   to: "/",                icon: LayoutDashboard, end: true },
  { label: "Devices",     to: "/devices",         icon: Activity },
  { label: "Alerts",      to: "/alerts",          icon: AlertTriangle },
  { label: "Recovery",    to: "/recovery-actions",icon: Wrench },
  { label: "Incidents",   to: "/incidents",       icon: ClipboardList },
  { label: "Alert Rules", to: "/alert-rules",     icon: Siren },
  { label: "Audit Logs",  to: "/audit-logs",      icon: ScrollText },
];

function SidebarNavItem({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        [
          "group flex items-center gap-3 border-l-2 py-2.5 pl-5 pr-4 text-sm font-medium transition-all duration-150",
          isActive
            ? "border-amber-400 bg-amber-400/6 text-amber-300"
            : "border-transparent text-slate-500 hover:border-slate-700 hover:bg-white/[0.02] hover:text-slate-200",
        ].join(" ")
      }
    >
      {({ isActive }) => {
        const Icon = item.icon;
        return (
          <>
            <Icon
              size={15}
              strokeWidth={isActive ? 2 : 1.8}
              className={
                isActive
                  ? "text-amber-400"
                  : "text-slate-600 transition-colors group-hover:text-slate-400"
              }
            />
            <span>{item.label}</span>
          </>
        );
      }}
    </NavLink>
  );
}

export function AppShell() {
  const location = useLocation();

  return (
    <div className="sentinelx-console flex">
      {/* ── Sidebar ──────────────────────────────────────── */}
      <aside className="sx-shell-aside fixed inset-y-0 left-0 hidden w-[220px] lg:flex lg:flex-col">
        {/* Logo */}
        <div
          className="flex shrink-0 items-center gap-3 border-b px-5 py-5"
          style={{ borderColor: "var(--sx-border)" }}
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded bg-amber-400 text-[11px] font-bold tracking-tight text-black">
            SX
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-amber-400">
              SentinelX
            </p>
            <p className="mt-0.5 text-[10px]" style={{ color: "var(--sx-dim)" }}>
              Operations Console
            </p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4">
          <p
            className="mb-1 px-5 text-[10px] font-semibold uppercase tracking-[0.2em]"
            style={{ color: "var(--sx-dim)" }}
          >
            Monitoring
          </p>
          <div>
            {primaryNavItems.map((item) => (
              <SidebarNavItem key={item.to} item={item} />
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div
          className="shrink-0 border-t px-5 py-4"
          style={{ borderColor: "var(--sx-border)" }}
        >
          <div className="flex items-center gap-2">
            <span
              className="sx-live-dot"
              style={{ color: "var(--sx-green)" }}
            />
            <span
              className="text-[10px] font-medium uppercase tracking-[0.16em]"
              style={{ color: "var(--sx-muted)" }}
            >
              Live
            </span>
          </div>
          <p className="mt-1 text-[10px]" style={{ color: "var(--sx-dim)" }}>
            FastAPI + PostgreSQL
          </p>
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────────────── */}
      <div className="flex min-h-dvh flex-1 flex-col lg:ml-[220px]">
        {/* Mobile header */}
        <header
          className="sticky top-0 z-20 flex items-center gap-3 border-b bg-[var(--sx-bg)] px-4 py-3 lg:hidden"
          style={{ borderColor: "var(--sx-border)" }}
        >
          <div className="flex size-7 items-center justify-center rounded bg-amber-400 text-[11px] font-bold text-black">
            SX
          </div>
          <span className="text-xs font-bold uppercase tracking-[0.18em] text-amber-400">
            SentinelX
          </span>
          <nav className="ml-2 flex gap-1 overflow-x-auto pb-0.5">
            {primaryNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 whitespace-nowrap rounded px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      isActive
                        ? "bg-amber-400/10 text-amber-300"
                        : "text-slate-500 hover:text-slate-200"
                    }`
                  }
                >
                  <Icon size={13} strokeWidth={1.8} />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>
        </header>

        {/* Page content — animated route transitions */}
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="flex flex-1 flex-col"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
