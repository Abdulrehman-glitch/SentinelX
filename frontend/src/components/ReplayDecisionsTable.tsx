import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getSeverityTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { ReplayDecision } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type ReplayDecisionsTableProps = {
  decisions: ReplayDecision[];
};

function riskTone(risk: ReplayDecision["operational_risk"]) {
  if (risk === "high") return "red" as const;
  if (risk === "medium") return "amber" as const;
  return "green" as const;
}

export function ReplayDecisionsTable({ decisions }: ReplayDecisionsTableProps) {
  const columns: ColumnDef<ReplayDecision>[] = [
    {
      accessorKey: "device_id",
      header: "Device",
      cell: ({ row }) => <span className="sx-mono text-xs">{truncateMiddle(row.original.device_id, 16)}</span>,
    },
    {
      accessorKey: "window_start",
      header: "Window",
      cell: ({ row }) => (
        <span className="text-xs">
          {formatDate(row.original.window_start)} → {formatDate(row.original.window_end)}
        </span>
      ),
    },
    {
      accessorKey: "detector_agreement",
      header: "Agreement",
      cell: ({ row }) => <span className="text-xs">{formatLabel(row.original.detector_agreement)}</span>,
    },
    {
      accessorKey: "combined_severity",
      header: "Severity",
      cell: ({ row }) => (
        <Badge tone={getSeverityTone(row.original.combined_severity)}>{row.original.combined_severity}</Badge>
      ),
    },
    {
      accessorKey: "operational_risk",
      header: "Risk",
      cell: ({ row }) => <Badge tone={riskTone(row.original.operational_risk)}>{row.original.operational_risk}</Badge>,
    },
    {
      accessorKey: "explanation",
      header: "Explanation",
      cell: ({ row }) => <span className="text-xs sx-c-muted">{row.original.explanation}</span>,
    },
  ];

  return (
    <DataTable
      title="Replayed Decisions"
      description="Read-only backtest of the hybrid pipeline over the requested window — never written to AnomalyPrediction or HybridDecision."
      data={decisions}
      columns={columns}
      searchPlaceholder="Search replayed decisions..."
      emptyMessage="No feature windows found in this period for the selected device class."
    />
  );
}
