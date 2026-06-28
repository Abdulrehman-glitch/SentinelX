import type { ReactNode } from "react";
import { useAuth } from "../contexts/AuthContext";
import type { UserRole } from "../types/api";

type PermissionGateProps = {
  roles: UserRole[];
  children: ReactNode;
  fallback?: ReactNode;
};

export function PermissionGate({
  roles,
  children,
  fallback = null,
}: PermissionGateProps) {
  const { hasRole } = useAuth();

  if (!hasRole(roles)) {
    return fallback;
  }

  return <>{children}</>;
}