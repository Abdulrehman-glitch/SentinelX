import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";
import { Badge, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { RecoveryCommand } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type RecoveryCommandsTableProps = {
  commands: RecoveryCommand[];
};

function riskTone(riskLevel: string) {
  if (riskLevel === "high") return "red" as const;
  if (riskLevel === "medium") return "amber" as const;
  return "green" as const;
}

export function RecoveryCommandsTable({ commands }: RecoveryCommandsTableProps) {
  const columns: ColumnDef<RecoveryCommand>[] = [
    {
      accessorKey: "device_id",
      header: "Device",
      cell: ({ row }) => (
        <Link to={`/recovery-commands/${row.original.id}`} className="font-semibold sx-c-text hover:underline">
          {truncateMiddle(row.original.device_id, 16)}
        </Link>
      ),
    },
    {
      accessorKey: "action_type",
      header: "Action",
      cell: ({ row }) => <span className="sx-mono text-xs">{row.original.action_type}</span>,
    },
    {
      accessorKey: "risk_level",
      header: "Risk",
      cell: ({ row }) => <Badge tone={riskTone(row.original.risk_level)}>{row.original.risk_level}</Badge>,
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <Badge tone={getStatusTone(row.original.status)}>{formatLabel(row.original.status)}</Badge>,
    },
    {
      accessorKey: "approval_mode",
      header: "Approval",
      cell: ({ row }) => formatLabel(row.original.approval_mode),
    },
    {
      accessorKey: "decision_source",
      header: "Source",
      cell: ({ row }) => (
        <Badge tone={row.original.decision_source === "ai_proposal" ? "violet" : "slate"}>
          {formatLabel(row.original.decision_source)}
        </Badge>
      ),
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => formatDate(row.original.created_at),
    },
  ];

  return (
    <DataTable
      title="Recovery Commands"
      description="Signed, verifiable, allowlisted commands dispatched to devices — separate from the passive recovery-action log."
      data={commands}
      columns={columns}
      searchPlaceholder="Search commands by device, action, or status..."
      emptyMessage="No recovery commands yet. Propose one manually or from an AI anomaly prediction."
    />
  );
}
