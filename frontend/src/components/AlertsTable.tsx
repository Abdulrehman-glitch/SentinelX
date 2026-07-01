import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getSeverityTone, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import { PermissionGate } from "./PermissionGate";
import type { Alert } from "../types/api";
import { formatDate, formatLabel } from "../utils/format";

type AlertsTableProps = {
  alerts: Alert[];
  resolvingAlertId: string | null;
  onResolveAlert: (alertId: string) => void;
};

function getAlertId(alert: Alert) {
  return alert.id ?? alert.alert_id ?? "";
}

function getAlertType(alert: Alert) {
  return alert.alert_type ?? alert.metric_type ?? "system";
}

function isAlertResolved(alert: Alert) {
  return alert.resolved ?? alert.is_resolved ?? false;
}

export function AlertsTable({
  alerts,
  resolvingAlertId,
  onResolveAlert,
}: AlertsTableProps) {
  const columns: ColumnDef<Alert>[] = [
    {
      id: "type",
      header: "Type",
      accessorFn: (row) => getAlertType(row),
      cell: ({ row }) => (
        <span className="font-semibold sx-c-text">
          {formatLabel(getAlertType(row.original))}
        </span>
      ),
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
      accessorKey: "message",
      header: "Message",
      cell: ({ row }) => row.original.message,
    },
    {
      id: "resolved",
      header: "Status",
      accessorFn: (row) => (isAlertResolved(row) ? "resolved" : "unresolved"),
      cell: ({ row }) => {
        const resolved = isAlertResolved(row.original);
        const label = resolved ? "resolved" : "unresolved";

        return <Badge tone={getStatusTone(label)}>{label}</Badge>;
      },
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => formatDate(row.original.created_at),
    },
    {
      id: "action",
      header: "Action",
      enableSorting: false,
      cell: ({ row }) => {
        const alert = row.original;
        const alertId = getAlertId(alert);
        const resolved = isAlertResolved(alert);

        return (
          <PermissionGate
            roles={["admin", "engineer"]}
            fallback={<span className="text-xs sx-c-text0">Read only</span>}
          >
            <button
              type="button"
              onClick={() => onResolveAlert(alertId)}
              disabled={resolved || !alertId || resolvingAlertId === alertId}
              className="sx-button-primary rounded-lg px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {resolvingAlertId === alertId
                ? "Resolving..."
                : resolved
                  ? "Resolved"
                  : "Resolve"}
            </button>
          </PermissionGate>
        );
      },
    },
  ];

  return (
    <DataTable
      title="Alerts"
      description="Rule-based warning and critical alerts generated from system metrics."
      data={alerts}
      columns={columns}
      searchPlaceholder="Search alerts by type, severity, status, or message..."
      emptyMessage="No alerts have been generated yet. Send a high CPU, memory, or disk metric to trigger alert creation."
    />
  );
}