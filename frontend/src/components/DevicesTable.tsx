import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";
import { Badge, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { Device } from "../types/api";
import { formatDate } from "../utils/format";

type DevicesTableProps = {
  devices: Device[];
};

function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

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
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        const deviceId = getDeviceId(row.original);

        if (!deviceId) {
          return <span className="text-slate-400">Unavailable</span>;
        }

        return (
          <Link
            to={`/devices/${encodeURIComponent(deviceId)}`}
            className="rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            View details
          </Link>
        );
      },
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