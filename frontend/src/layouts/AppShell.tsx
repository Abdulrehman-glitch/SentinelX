import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BrainCircuit,
  ClipboardList,
  Command,
  FileText,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  PlugZap,
  ScrollText,
  ShieldAlert,
  Settings,
  Siren,
  UserCog,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";
import { LoadingScreen } from "../components/LoadingScreen";
import { useAuth } from "../contexts/AuthContext";
import { useUserSettingsQuery } from "../hooks/useUserSettingsQuery";
import type { UserRole } from "../types/api";
import { applyAccessibilitySettings, persistUiSettings } from "../utils/accessibility";
import { NavDock } from "./NavDock";

type MobileNavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  end?: boolean;
  roles?: UserRole[];
};

const MOBILE_NAV_ITEMS: MobileNavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard, end: true },
  { label: "Fleet", to: "/devices", icon: Activity },
  { label: "Metrics", to: "/metrics", icon: BarChart3 },
  { label: "Anomalies", to: "/anomalies", icon: BrainCircuit },
  { label: "Alerts", to: "/alerts", icon: AlertTriangle },
  { label: "Notifications", to: "/notifications", icon: Bell },
  { label: "Recovery", to: "/recovery-actions", icon: Wrench },
  { label: "Command", to: "/recovery-command", icon: Command },
  { label: "Incidents", to: "/incidents", icon: ClipboardList },
  { label: "Reports", to: "/reports", icon: FileText },
  { label: "Rules", to: "/alert-rules", icon: Siren, roles: ["admin", "owner", "platform_admin"] },
  { label: "Audit Logs", to: "/audit-logs", icon: ScrollText, roles: ["admin", "owner", "platform_admin"] },
  { label: "Security Logs", to: "/security-logs", icon: ShieldAlert, roles: ["admin", "owner", "platform_admin"] },
  { label: "Users", to: "/users", icon: UserCog, roles: ["admin", "owner", "platform_admin"] },
  { label: "Tokens", to: "/device-credentials", icon: KeyRound, roles: ["admin", "owner", "platform_admin"] },
  { label: "Fleet Setup", to: "/agent-setup", icon: PlugZap, roles: ["admin", "owner", "platform_admin"] },
  { label: "Settings", to: "/settings", icon: Settings },
];

export function AppShell() {
  const { user, logout, showLoadingScreen, dismissLoadingScreen } = useAuth();
  const [dockCollapsed, setDockCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const settingsQuery = useUserSettingsQuery();

  useEffect(() => {
    if (settingsQuery.data) {
      persistUiSettings(settingsQuery.data);
      applyAccessibilitySettings(settingsQuery.data);
    }
  }, [settingsQuery.data]);

  const initials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : "SX";

  const visibleMobileItems = MOBILE_NAV_ITEMS.filter((item) => {
    if (!item.roles) return true;
    if (!user?.role) return false;
    return item.roles.includes(user.role as UserRole);
  });

  if (showLoadingScreen) {
    return <LoadingScreen onComplete={dismissLoadingScreen} />;
  }

  return (
    <div className="sx-shell">
      {/* ── Desktop NavDock ───────────────────────────────────── */}
      <div className="sx-shell-dock hidden lg:block">
        <NavDock
          collapsed={dockCollapsed}
          onToggle={() => setDockCollapsed((c) => !c)}
        />
      </div>

      {/* ── Main content ──────────────────────────────────────── */}
      <div
        className={`sx-shell-main${dockCollapsed ? " sx-dock-is-collapsed" : ""}`}
      >
        {/* Top bar */}
        <header className="sx-shell-topbar">
          <div className="sx-topbar-left">
            {/* Mobile menu toggle */}
            <button
              type="button"
              className="sx-topbar-menu-btn lg:hidden"
              onClick={() => setMobileOpen((o) => !o)}
              aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={mobileOpen}
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Brand (mobile) */}
            <div className="flex items-center gap-2 lg:hidden">
              <div className="sx-topbar-badge">SX</div>
              <span className="sx-topbar-brand">SentinelX</span>
            </div>

            {/* Live status (desktop) */}
            <div className="hidden lg:flex items-center gap-2">
              <span className="sx-live-dot" />
              <span className="sx-topbar-live-text">System operational</span>
            </div>
          </div>

          <div className="sx-topbar-right">
            <NavLink to="/notifications" className="sx-topbar-icon-btn" title="Notifications">
              <Bell size={17} />
            </NavLink>
            <div className="sx-topbar-avatar" title={user?.full_name ?? "User"}>
              {initials}
            </div>
          </div>
        </header>

        {/* Mobile nav overlay */}
        {mobileOpen && (
          <div
            className="sx-mobile-nav lg:hidden"
            role="navigation"
            aria-label="Mobile navigation"
          >
            {/* User info header */}
            <div className="sx-mobile-nav-user">
              <div className="sx-mobile-nav-avatar">{initials}</div>
              <div>
                <p className="sx-mobile-nav-name">{user?.full_name ?? "User"}</p>
                <p className="sx-mobile-nav-role">{user?.role ?? "viewer"}</p>
              </div>
            </div>

            <div className="sx-mobile-nav-divider" />

            {/* Nav items */}
            <div className="sx-mobile-nav-items">
              {visibleMobileItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      ["sx-mobile-nav-item", isActive ? "active" : ""].join(" ").trim()
                    }
                  >
                    <Icon size={16} strokeWidth={1.8} className="sx-mobile-nav-icon" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </div>

            <div className="sx-mobile-nav-divider" />

            {/* Sign out */}
            <button
              type="button"
              className="sx-mobile-nav-signout"
              onClick={() => { logout(); setMobileOpen(false); }}
            >
              <LogOut size={15} />
              <span>Sign out</span>
            </button>
          </div>
        )}

        {/* Page content */}
        <main className="sx-shell-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
