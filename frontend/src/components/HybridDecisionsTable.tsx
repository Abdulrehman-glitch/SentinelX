import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";
import { Badge, getSeverityTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { HybridDecision } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type HybridDecisionsTableProps = {
  decisions: HybridDecision[];
};

function agreementTone(agreement: HybridDecision["detector_agreement"]) {
  if (agreement === "all_agree") return "red" as const;
  if (agreement === "two_agree") return "amber" as const;
  if (agreement === "detector_conflict") return "blue" as const;
  if (agreement === "all_normal") return "green" as const;
  if (agreement === "insufficient_data") return "slate" as const;
  return "violet" as const;
}

function riskTone(risk: HybridDecision["operational_risk"]) {
  if (risk === "high") return "red" as const;
  if (risk === "medium") return "amber" as const;
  return "green" as const;
}

function reviewStatusTone(status: HybridDecision["review_status"]) {
  if (status === "true_positive") return "red" as const;
  if (status === "false_positive") return "green" as const;
  if (status === "expected_change") return "blue" as const;
  if (status === "insufficient_context" || status === "duplicate") return "amber" as const;
  return "slate" as const;
}

export function HybridDecisionsTable({ decisions }: HybridDecisionsTableProps) {
  const columns: ColumnDef<HybridDecision>[] = [
    {
      accessorKey: "device_id",
      header: "Device",
      cell: ({ row }) => (
        <Link to={`/hybrid-decisions/${row.original.id}`} className="font-semibold sx-c-text hover:underline">
          {truncateMiddle(row.original.device_id, 16)}
        </Link>
      ),
    },
    {
      accessorKey: "detector_agreement",
      header: "Agreement",
      cell: ({ row }) => (
        <Badge tone={agreementTone(row.original.detector_agreement)}>
          {formatLabel(row.original.detector_agreement)}
        </Badge>
      ),
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
      accessorKey: "confidence",
      header: "Confidence",
      cell: ({ row }) => formatLabel(row.original.confidence),
    },
    {
      accessorKey: "review_status",
      header: "Review",
      cell: ({ row }) => (
        <Badge tone={reviewStatusTone(row.original.review_status)}>{formatLabel(row.original.review_status)}</Badge>
      ),
    },
    {
      accessorKey: "created_at",
      header: "Scored",
      cell: ({ row }) => formatDate(row.original.created_at),
    },
  ];

  return (
    <DataTable
      title="Hybrid Decisions"
      description="One combined judgement per feature window — deterministic alert rules plus the statistical baseline plus IsolationForest, never lower than a fired rule's severity."
      data={decisions}
      columns={columns}
      searchPlaceholder="Search decisions by device, agreement, or review status..."
      emptyMessage="No hybrid decisions yet. Run the hybrid detection pipeline for a device with enough history to see combined judgements here."
    />
  );
}
