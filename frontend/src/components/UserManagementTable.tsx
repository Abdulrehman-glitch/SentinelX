import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import {
  useDeactivateUserMutation,
  useUpdateUserRoleMutation,
} from "../hooks/useSecurityMutations";
import type { AuthUser, UserRole } from "../types/api";
import { formatDate } from "../utils/format";

type UserManagementTableProps = {
  users: AuthUser[];
};

export function UserManagementTable({ users }: UserManagementTableProps) {
  const updateRoleMutation = useUpdateUserRoleMutation();
  const deactivateUserMutation = useDeactivateUserMutation();

  const columns: ColumnDef<AuthUser>[] = [
    {
      accessorKey: "full_name",
      header: "User",
      cell: ({ row }) => (
        <div>
          <p className="font-semibold sx-c-text">{row.original.full_name}</p>
          <p className="mt-1 text-xs sx-c-text0">{row.original.email}</p>
        </div>
      ),
    },
    {
      accessorKey: "role",
      header: "Role",
      cell: ({ row }) => <Badge tone="blue">{row.original.role}</Badge>,
    },
    {
      accessorKey: "is_active",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={getStatusTone(row.original.is_active ? "online" : "offline")}>
          {row.original.is_active ? "active" : "inactive"}
        </Badge>
      ),
    },
    {
      accessorKey: "last_login_at",
      header: "Last Login",
      cell: ({ row }) => formatDate(row.original.last_login_at),
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => formatDate(row.original.created_at),
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        const user = row.original;

        return (
          <div className="flex flex-wrap gap-2">
            <select
              value={user.role}
              onChange={(event) =>
                updateRoleMutation.mutate({
                  userId: user.id,
                  role: event.target.value as UserRole,
                })
              }
              className="sx-input rounded-lg px-2 py-2 text-xs outline-none"
              disabled={updateRoleMutation.isPending || !user.is_active}
            >
              <option value="admin">admin</option>
              <option value="engineer">engineer</option>
              <option value="viewer">viewer</option>
            </select>

            <button
              type="button"
              onClick={() => deactivateUserMutation.mutate(user.id)}
              disabled={deactivateUserMutation.isPending || !user.is_active}
              className="sx-button-secondary rounded-lg px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              Deactivate
            </button>
          </div>
        );
      },
    },
  ];

  return (
    <DataTable
      title="User Management"
      description="Admin-only user and role management for SentinelX access control."
      data={users}
      columns={columns}
      searchPlaceholder="Search users by name, email, role, or status..."
      emptyMessage="No users have been created yet."
    />
  );
}