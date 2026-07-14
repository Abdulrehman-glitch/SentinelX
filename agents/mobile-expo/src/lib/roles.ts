// Mirrors ROLE_HIERARCHY in backend/app/api/deps.py — keep in sync.

export type Role = "platform_admin" | "owner" | "admin" | "engineer" | "operator" | "viewer";

export const ROLE_HIERARCHY: Record<Role, number> = {
  platform_admin: 60,
  owner: 50,
  admin: 40,
  engineer: 30,
  operator: 20,
  viewer: 10,
};

export function isRole(value: string): value is Role {
  return value in ROLE_HIERARCHY;
}

export function hasMinRole(role: string | undefined, min: Role): boolean {
  if (!role || !isRole(role)) return false;
  return ROLE_HIERARCHY[role] >= ROLE_HIERARCHY[min];
}

// Permission helpers used by screens; the server enforces the same rules.
// Role sets mirror the exact require_role() lists in the backend routes.
export const can = {
  // alerts.py resolve_alert: admin | engineer | owner
  resolveAlerts: (role?: string) => role === "admin" || role === "engineer" || role === "owner",
  manageIncidents: (role?: string) => hasMinRole(role, "engineer"),
  requestRecovery: (role?: string) => hasMinRole(role, "engineer"),
  manageDevices: (role?: string) => hasMinRole(role, "admin"),
  manageCredentials: (role?: string) => hasMinRole(role, "admin"),
  selfProvisionAgent: (role?: string) => hasMinRole(role, "admin"),
  // audit_logs.py: admin | owner | operator | platform_admin (no engineer/viewer)
  viewAuditLogs: (role?: string) =>
    role === "admin" || role === "owner" || role === "operator" || role === "platform_admin",
};
