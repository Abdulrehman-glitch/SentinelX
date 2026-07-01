import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getSeverityTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { AuditLog } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type AuditLogsTableProps = {
  auditLogs: AuditLog[];
};

export function AuditLogsTable({ auditLogs }: AuditLogsTableProps) {
  const columns: ColumnDef<AuditLog>[] = [
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
          {row.original.severity}
        </Badge>
      ),
    },
    {
      accessorKey: "action",
      header: "Action",
      cell: ({ row }) => (
        <span className="font-semibold sx-c-text">
          {formatLabel(row.original.action)}
        </span>
      ),
    },
    {
      accessorKey: "actor_type",
      header: "Actor",
      cell: ({ row }) =>
        `${formatLabel(row.original.actor_type)}${
          row.original.actor_id ? ` · ${row.original.actor_id}` : ""
        }`,
    },
    {
      accessorKey: "target_type",
      header: "Target",
      cell: ({ row }) => {
        const target = row.original.target_type
          ? formatLabel(row.original.target_type)
          : "System";

        return row.original.target_id
          ? `${target} · ${truncateMiddle(row.original.target_id, 22)}`
          : target;
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
      title="Audit Logs"
      description="Traceable system actions recorded across devices, alerts, incidents, rules, and recovery workflows."
      data={auditLogs}
      columns={columns}
      searchPlaceholder="Search audit logs by action, actor, target, severity, or message..."
      emptyMessage="No audit logs have been recorded yet."
    />
  );
}