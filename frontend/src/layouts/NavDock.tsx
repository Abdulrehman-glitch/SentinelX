import {
  Activity,
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Command,
  FileText,
  LayoutDashboard,
  LogOut,
  PlugZap,
  ScanSearch,
  ScrollText,
  Settings,
  Siren,
  UserCog,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router";
import { useAuth } from "../contexts/AuthContext";
import type { UserRole } from "../types/api";

type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  end?: boolean;
  roles?: UserRole[];
};

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard, end: true },
  { label: "Fleet", to: "/devices", icon: Activity },
  { label: "Metrics", to: "/metrics", icon: BarChart3 },
  { label: "Anomalies", to: "/anomalies", icon: BrainCircuit },
  { label: "AI Predictions", to: "/anomaly-predictions", icon: ScanSearch },
  { label: "Alerts", to: "/alerts", icon: AlertTriangle },
  { label: "Recovery", to: "/recovery-actions", icon: Wrench },
  { label: "Command", to: "/recovery-command", icon: Command },
  { label: "Incidents", to: "/incidents", icon: ClipboardList },
  { label: "Reports", to: "/reports", icon: FileText },
  { label: "Rules", to: "/alert-rules", icon: Siren, roles: ["admin", "owner", "platform_admin"] },
  { label: "Audit", to: "/audit-logs", icon: ScrollText, roles: ["admin", "owner", "platform_admin"] },
  { label: "Users", to: "/users", icon: UserCog, roles: ["admin", "owner", "platform_admin"] },
  { label: "Fleet Setup", to: "/agent-setup", icon: PlugZap, roles: ["admin", "owner", "platform_admin"] },
  { label: "Settings", to: "/settings", icon: Settings },
];

function canSee(userRole: UserRole | undefined, item: NavItem) {
  if (!item.roles) return true;
  if (!userRole) return false;
  return item.roles.includes(userRole as UserRole);
}

type Props = {
  collapsed: boolean;
  onToggle: () => void;
};

export function NavDock({ collapsed, onToggle }: Props) {
  const { user, logout } = useAuth();
  const [hovered, setHovered] = useState<string | null>(null);

  const initials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : "SX";

  const visibleItems = NAV_ITEMS.filter((item) =>
    canSee(user?.role as UserRole | undefined, item)
  );

  return (
    <aside className={`sx-dock ${collapsed ? "sx-dock-collapsed" : ""}`}>
      {/* Logo */}
      <div className="sx-dock-logo">
        <div className="sx-dock-logo-badge">
          <img src="/brand/sentinelx-mark.png" alt="" className="sx-brand-mark" />
        </div>
        {!collapsed && (
          <div className="sx-dock-logo-text">
            <span className="sx-dock-logo-name">
              Sentinel<span className="sx-wordmark-x">X</span>
            </span>
            <span className="sx-dock-logo-sub">Detect · Defend · Recover</span>
          </div>
        )}
      </div>

      {/* Live indicator */}
      {!collapsed && (
        <div className="sx-dock-live">
          <span className="sx-live-dot" />
          <span className="sx-dock-live-text">Connected · v2.0</span>
        </div>
      )}

      {/* Nav items */}
      <nav className="sx-dock-nav" aria-label="Main navigation">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.to}
              className="sx-dock-item-wrap"
              onMouseEnter={() => setHovered(item.to)}
              onMouseLeave={() => setHovered(null)}
            >
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  ["sx-dock-item", isActive ? "sx-dock-item-active" : ""].join(" ").trim()
                }
              >
                <Icon size={17} strokeWidth={1.8} className="sx-dock-icon" />
                {!collapsed && <span className="sx-dock-label">{item.label}</span>}
              </NavLink>

              {/* Tooltip when collapsed */}
              {collapsed && hovered === item.to && (
                <div className="sx-dock-tooltip">{item.label}</div>
              )}
            </div>
          );
        })}
      </nav>

      {/* User area (pinned to bottom) */}
      <div className="sx-dock-user">
        <div className="sx-dock-user-avatar">{initials}</div>
        {!collapsed && (
          <div className="sx-dock-user-info">
            <span className="sx-dock-user-name">{user?.full_name ?? "User"}</span>
            <span className="sx-dock-user-role">{user?.role ?? "viewer"}</span>
          </div>
        )}
      </div>

      <button type="button" onClick={() => logout()} className="sx-dock-logout" title="Sign out">
        <LogOut size={15} />
        {!collapsed && <span>Sign out</span>}
      </button>

      {/* Collapse toggle */}
      <button
        type="button"
        onClick={onToggle}
        className="sx-dock-toggle"
        title={collapsed ? "Expand navigation" : "Collapse navigation"}
        aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  );
}
