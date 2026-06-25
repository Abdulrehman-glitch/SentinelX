import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { RecoveryAction } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type RecoveryActionsTableProps = {
  recoveryActions: RecoveryAction[];
};

export function RecoveryActionsTable({
  recoveryActions,
}: RecoveryActionsTableProps) {
  const columns: ColumnDef<RecoveryAction>[] = [
    {
      accessorKey: "action_type",
      header: "Action Type",
      cell: ({ row }) => (
        <span className="font-medium text-slate-950">
          {formatLabel(row.original.action_type)}
        </span>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={getStatusTone(row.original.status)}>
          {row.original.status}
        </Badge>
      ),
    },
    {
      accessorKey: "device_id",
      header: "Device ID",
      cell: ({ row }) =>
        row.original.device_id ? truncateMiddle(row.original.device_id) : "Not linked",
    },
    {
      accessorKey: "details",
      header: "Details",
      cell: ({ row }) => row.original.details ?? "No details recorded",
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => formatDate(row.original.created_at),
    },
  ];

  return (
    <DataTable
      title="Recovery Actions"
      description="Non-destructive self-healing actions logged by SentinelX for safety, traceability, and project evidence."
      data={recoveryActions}
      columns={columns}
      searchPlaceholder="Search recovery actions by type, status, device, or details..."
      emptyMessage="No recovery actions have been logged yet. Trigger or manually log a recovery action through the backend API to verify this table."
    />
  );
}