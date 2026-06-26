import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "./DataTable";
import type { SystemMetric } from "../types/api";
import { formatDate } from "../utils/format";

type MetricsHistoryTableProps = {
  metrics: SystemMetric[];
};

function getMetricTimestamp(metric: SystemMetric) {
  return (
    metric.created_at ??
    metric.recorded_at ??
    metric.timestamp ??
    metric.updated_at ??
    ""
  );
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

export function MetricsHistoryTable({ metrics }: MetricsHistoryTableProps) {
  const columns: ColumnDef<SystemMetric>[] = [
    {
      id: "created_at",
      header: "Recorded",
      accessorFn: (row) => getMetricTimestamp(row),
      cell: ({ row }) => formatDate(getMetricTimestamp(row.original)),
    },
    {
      accessorKey: "cpu_percent",
      header: "CPU",
      cell: ({ row }) => (
        <span className="font-medium text-slate-950">
          {formatPercent(row.original.cpu_percent)}
        </span>
      ),
    },
    {
      accessorKey: "memory_percent",
      header: "Memory",
      cell: ({ row }) => formatPercent(row.original.memory_percent),
    },
    {
      accessorKey: "disk_percent",
      header: "Disk",
      cell: ({ row }) => formatPercent(row.original.disk_percent),
    },
  ];

  return (
    <DataTable
      title="Metric History"
      description="Recent CPU, memory, and disk telemetry records for this device."
      data={metrics}
      columns={columns}
      searchPlaceholder="Search metric values or timestamps..."
      emptyMessage="No metric history is available for this device yet."
    />
  );
}