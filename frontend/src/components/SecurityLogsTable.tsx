import type { ColumnDef } from "@tanstack/react-table";
import type { SecurityLog } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";
import { Badge, getSeverityTone } from "./Badge";
import { DataTable } from "./DataTable";

type SecurityLogsTableProps = {
  securityLogs: SecurityLog[];
};

export function SecurityLogsTable({ securityLogs }: SecurityLogsTableProps) {
  const columns: ColumnDef<SecurityLog>[] = [
    {
      accessorKey: "created_at",
      header: "Time",
      cell: ({ row }) => formatDate(row.original.created_at),
    },
    {
      accessorKey: "severity",
      header: "Severity",
      cell: ({ row }) => (
        <Badge tone={getSeverityTone(row.original.severity)}>
          {formatLabel(row.original.severity)}
        </Badge>
      ),
    },
    {
      accessorKey: "event_type",
      header: "Event",
      cell: ({ row }) => (
        <span className="font-semibold" style={{ color: "var(--sx-text)" }}>
          {formatLabel(row.original.event_type)}
        </span>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => formatLabel(row.original.status),
    },
    {
      accessorKey: "actor_type",
      header: "Actor",
      cell: ({ row }) => {
        const actor = formatLabel(row.original.actor_type);
        return row.original.actor_id
          ? `${actor} · ${truncateMiddle(row.original.actor_id, 18)}`
          : actor;
      },
    },
    {
      accessorKey: "ip_address",
      header: "IP",
      cell: ({ row }) => row.original.ip_address ?? "—",
    },
    {
      accessorKey: "resource_type",
      header: "Resource",
      cell: ({ row }) => {
        const resource = row.original.resource_type
          ? formatLabel(row.original.resource_type)
          : "System";

        return row.original.resource_id
          ? `${resource} · ${truncateMiddle(row.original.resource_id, 18)}`
          : resource;
      },
    },
    {
      accessorKey: "message",
      header: "Message",
      cell: ({ row }) => row.original.message,
    },
  ];

  return (
    <DataTable
      title="Security Logs"
      description="Security events including login failures, unauthorized access, token issues, and rate-limit violations."
      data={securityLogs}
      columns={columns}
      searchPlaceholder="Search security logs by event, actor, IP, status, severity, or message..."
      emptyMessage="No security logs have been recorded yet."
    />
  );
}
