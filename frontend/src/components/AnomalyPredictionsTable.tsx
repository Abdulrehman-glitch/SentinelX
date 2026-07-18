import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";
import { Badge } from "./Badge";
import { DataTable } from "./DataTable";
import type { AnomalyPrediction } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type AnomalyPredictionsTableProps = {
  predictions: AnomalyPrediction[];
};

function confidenceTone(confidence: AnomalyPrediction["confidence"]) {
  if (confidence === "high") return "red" as const;
  if (confidence === "medium") return "amber" as const;
  return "slate" as const;
}

function reviewStatusTone(status: AnomalyPrediction["review_status"]) {
  if (status === "true_positive") return "red" as const;
  if (status === "false_positive") return "green" as const;
  if (status === "expected_change") return "blue" as const;
  if (status === "insufficient_context") return "amber" as const;
  return "slate" as const;
}

export function AnomalyPredictionsTable({ predictions }: AnomalyPredictionsTableProps) {
  const columns: ColumnDef<AnomalyPrediction>[] = [
    {
      accessorKey: "device_id",
      header: "Device",
      cell: ({ row }) => (
        <Link to={`/anomaly-predictions/${row.original.id}`} className="font-semibold sx-c-text hover:underline">
          {truncateMiddle(row.original.device_id, 16)}
        </Link>
      ),
    },
    {
      accessorKey: "model_name",
      header: "Model",
      cell: ({ row }) => <span className="sx-mono text-xs">{row.original.model_name}</span>,
    },
    {
      accessorKey: "anomaly_score",
      header: "Score",
      cell: ({ row }) => row.original.anomaly_score.toFixed(3),
    },
    {
      accessorKey: "confidence",
      header: "Confidence",
      cell: ({ row }) => <Badge tone={confidenceTone(row.original.confidence)}>{row.original.confidence}</Badge>,
    },
    {
      accessorKey: "is_anomalous",
      header: "Anomalous",
      cell: ({ row }) => (
        <Badge tone={row.original.is_anomalous ? "red" : "green"}>
          {row.original.is_anomalous ? "Yes" : "No"}
        </Badge>
      ),
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
      title="Anomaly Predictions"
      description="Shadow-mode statistical baseline and IsolationForest predictions, awaiting human review."
      data={predictions}
      columns={columns}
      searchPlaceholder="Search predictions by device, model, or review status..."
      emptyMessage="No predictions yet. Run the observability pipeline for a device with enough history to see shadow-mode predictions here."
    />
  );
}
