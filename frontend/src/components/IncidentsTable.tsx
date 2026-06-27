import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";
import { Badge, getSeverityTone, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { Incident } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

type IncidentsTableProps = {
  incidents: Incident[];
};

export function IncidentsTable({ incidents }: IncidentsTableProps) {
  const columns: ColumnDef<Incident>[] = [
    {
      accessorKey: "title",
      header: "Incident",
      cell: ({ row }) => (
        <div>
          <p className="font-semibold text-slate-50">{row.original.title}</p>
          <p className="mt-1 text-xs text-slate-500">
            {truncateMiddle(row.original.id, 24)}
          </p>
        </div>
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
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={getStatusTone(row.original.status)}>
          {row.original.status}
        </Badge>
      ),
    },
    {
      accessorKey: "source",
      header: "Source",
      cell: ({ row }) => formatLabel(row.original.source),
    },
    {
      accessorKey: "device_id",
      header: "Device",
      cell: ({ row }) =>
        row.original.device_id
          ? truncateMiddle(row.original.device_id, 22)
          : "Not linked",
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
        <Link
          to={`/incidents/${encodeURIComponent(row.original.id)}`}
          className="sx-button-primary rounded-lg px-3 py-2 text-xs font-semibold"
        >
          Open timeline
        </Link>
      ),
    },
  ];

  return (
    <DataTable
      title="Incidents"
      description="Operational incidents grouped from alerts, device problems, or manual engineering review."
      data={incidents}
      columns={columns}
      searchPlaceholder="Search incidents by title, status, severity, source, or device..."
      emptyMessage="No incidents have been created yet."
    />
  );
}