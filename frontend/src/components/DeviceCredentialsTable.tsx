import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import { useRevokeDeviceCredentialMutation } from "../hooks/useSecurityMutations";
import type { DeviceCredential } from "../types/api";
import { formatDate, truncateMiddle } from "../utils/format";

type DeviceCredentialsTableProps = {
  credentials: DeviceCredential[];
};

export function DeviceCredentialsTable({
  credentials,
}: DeviceCredentialsTableProps) {
  const revokeMutation = useRevokeDeviceCredentialMutation();

  const columns: ColumnDef<DeviceCredential>[] = [
    {
      accessorKey: "name",
      header: "Credential",
      cell: ({ row }) => (
        <div>
          <p className="font-semibold text-slate-50">{row.original.name}</p>
          <p className="mt-1 font-mono text-xs text-slate-500">
            {row.original.token_preview}
          </p>
        </div>
      ),
    },
    {
      accessorKey: "device_id",
      header: "Device",
      cell: ({ row }) =>
        row.original.device_id
          ? truncateMiddle(row.original.device_id, 24)
          : "Not linked",
    },
    {
      accessorKey: "is_active",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={getStatusTone(row.original.is_active ? "online" : "offline")}>
          {row.original.is_active ? "active" : "revoked"}
        </Badge>
      ),
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => formatDate(row.original.created_at),
    },
    {
      accessorKey: "revoked_at",
      header: "Revoked",
      cell: ({ row }) => formatDate(row.original.revoked_at),
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => revokeMutation.mutate(row.original.id)}
          disabled={revokeMutation.isPending || !row.original.is_active}
          className="sx-button-secondary rounded-lg px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
        >
          Revoke
        </button>
      ),
    },
  ];

  return (
    <DataTable
      title="Device Credentials"
      description="Agent API credentials used for secure SentinelX device onboarding."
      data={credentials}
      columns={columns}
      searchPlaceholder="Search credentials by name, token preview, status, or device..."
      emptyMessage="No device credentials have been created yet."
    />
  );
}