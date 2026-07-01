import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BrainCircuit,
  ClipboardList,
  Command,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeft,
  PlugZap,
  ScrollText,
  Settings,
  Siren,
  UserCog,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { CookieConsent } from "../components/CookieConsent";
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
  { label: "Recovery", to: "/recovery-actions", icon: Wrench },
  { label: "Command", to: "/recovery-command", icon: Command },
  { label: "Incidents", to: "/incidents", icon: ClipboardList },
  { label: "Reports", to: "/reports", icon: FileText },
  { label: "Rules", to: "/alert-rules", icon: Siren, roles: ["admin", "owner", "platform_admin"] },
  { label: "Audit Logs", to: "/audit-logs", icon: ScrollText, roles: ["admin", "owner", "platform_admin"] },
  { label: "Users", to: "/users", icon: UserCog, roles: ["admin", "owner", "platform_admin"] },
  { label: "Fleet Setup", to: "/agent-setup", icon: PlugZap, roles: ["admin", "owner", "platform_admin"] },
  { label: "Settings", to: "/settings", icon: Settings },
];

// Page titles shown in the topbar for context.
const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/devices": "Fleet",
  "/metrics": "Metrics Explorer",
  "/anomalies": "Anomaly Centre",
  "/alerts": "Alerts",
  "/notifications": "Notifications",
  "/recovery-actions": "Recovery Actions",
  "/recovery-command": "Recovery Command",
  "/incidents": "Incidents",
  "/reports": "Reports",
  "/alert-rules": "Alert Rules",
  "/audit-logs": "Audit Logs",
  "/users": "User Management",
  "/agent-setup": "Fleet Setup",
  "/settings": "Settings",
  "/profile": "Profile",
};

function pageTitleFor(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  const match = Object.keys(PAGE_TITLES).find((p) => pathname.startsWith(p) && p !== "/");
  return match ? PAGE_TITLES[match] : "Console";
}

export function AppShell() {
  const { user, logout, showLoadingScreen, dismissLoadingScreen } = useAuth();
  const [dockCollapsed, setDockCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const settingsQuery = useUserSettingsQuery();
  const location = useLocation();
  const pageTitle = pageTitleFor(location.pathname);

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
      {/* Cookie / storage consent (shown once, after login) */}
      <CookieConsent />

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
            {/* Desktop: collapse / expand the sidebar */}
            <button
              type="button"
              className="sx-topbar-menu-btn sx-toggle-desktop"
              onClick={() => setDockCollapsed((c) => !c)}
              aria-label={dockCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!dockCollapsed}
              title={dockCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <PanelLeft size={18} />
            </button>

            {/* Mobile: open / close the navigation overlay */}
            <button
              type="button"
              className="sx-topbar-menu-btn sx-toggle-mobile"
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

            {/* Page title (desktop) */}
            <span className="sx-topbar-title hidden lg:block">{pageTitle}</span>
          </div>

          <div className="sx-topbar-right">
            {/* Live status pill */}
            <span className="sx-topbar-live">
              <span className="sx-live-dot" />
              <span className="sx-topbar-live-text">System operational</span>
            </span>
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
