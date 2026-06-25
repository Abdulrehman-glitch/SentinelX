import type { ColumnDef } from "@tanstack/react-table";
import { Badge, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { Device } from "../types/api";
import { formatDate } from "../utils/format";

type DevicesTableProps = {
  devices: Device[];
};

export function DevicesTable({ devices }: DevicesTableProps) {
  const columns: ColumnDef<Device>[] = [
    {
      accessorKey: "hostname",
      header: "Hostname",
      cell: ({ row }) => (
        <span className="font-medium text-slate-950">
          {row.original.hostname}
        </span>
      ),
    },
    {
      accessorKey: "ip_address",
      header: "IP Address",
      cell: ({ row }) => row.original.ip_address,
    },
    {
      accessorKey: "os_name",
      header: "Operating System",
      cell: ({ row }) => row.original.os_name,
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => {
        const status = row.original.status ?? "unknown";

        return <Badge tone={getStatusTone(status)}>{status}</Badge>;
      },
    },
    {
      id: "last_seen",
      header: "Last Seen",
      accessorFn: (row) => row.last_seen ?? row.updated_at ?? "",
      cell: ({ row }) => formatDate(row.original.last_seen ?? row.original.updated_at),
    },
  ];

  return (
    <DataTable
      title="Registered Devices"
      description="Monitored machines and agents registered with the SentinelX backend."
      data={devices}
      columns={columns}
      searchPlaceholder="Search devices by hostname, IP, OS, or status..."
      emptyMessage="No devices have been registered yet. Start the SentinelX agent or register a device through the API."
    />
  );
}