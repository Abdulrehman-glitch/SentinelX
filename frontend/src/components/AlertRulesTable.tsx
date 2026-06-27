import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getSeverityTone, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { AlertRule } from "../types/api";
import { useToggleAlertRuleMutation } from "../hooks/useOperationalMutations";
import { formatDate, formatLabel } from "../utils/format";

type AlertRulesTableProps = {
  alertRules: AlertRule[];
};

export function AlertRulesTable({ alertRules }: AlertRulesTableProps) {
  const toggleMutation = useToggleAlertRuleMutation();

  const columns: ColumnDef<AlertRule>[] = [
    {
      accessorKey: "name",
      header: "Rule",
      cell: ({ row }) => (
        <div>
          <p className="font-semibold text-slate-50">{row.original.name}</p>
          <p className="mt-1 text-xs text-slate-500">
            Cooldown: {row.original.cooldown_seconds}s
          </p>
        </div>
      ),
    },
    {
      accessorKey: "metric_type",
      header: "Metric",
      cell: ({ row }) => formatLabel(row.original.metric_type),
    },
    {
      id: "condition",
      header: "Condition",
      accessorFn: (row) => `${row.metric_type} ${row.operator} ${row.threshold}`,
      cell: ({ row }) =>
        `${formatLabel(row.original.metric_type)} ${row.original.operator} ${row.original.threshold}%`,
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
      accessorKey: "enabled",
      header: "State",
      cell: ({ row }) => (
        <Badge tone={getStatusTone(row.original.enabled ? "online" : "offline")}>
          {row.original.enabled ? "enabled" : "disabled"}
        </Badge>
      ),
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
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => toggleMutation.mutate(row.original.id)}
          disabled={toggleMutation.isPending}
          className="sx-button-primary rounded-lg px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        >
          {row.original.enabled ? "Disable" : "Enable"}
        </button>
      ),
    },
  ];

  return (
    <DataTable
      title="Alert Rules"
      description="Configurable threshold rules used to create warning and critical alerts from telemetry."
      data={alertRules}
      columns={columns}
      searchPlaceholder="Search rules by name, metric, severity, state, or condition..."
      emptyMessage="No alert rules have been configured yet."
    />
  );
}