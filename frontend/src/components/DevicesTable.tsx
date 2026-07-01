import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";
import { Badge, getStatusTone } from "./Badge";
import { DataTable } from "./DataTable";
import type { Device } from "../types/api";
import { formatRelativeTime, lastSeenStatus } from "../utils/format";

const LAST_SEEN_DOT: Record<"online" | "idle" | "offline", string> = {
  online: "var(--sx-green)",
  idle: "var(--sx-amber)",
  offline: "var(--sx-dim)",
};

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
        <span className="font-semibold" style={{ color: "var(--sx-text)" }}>
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
      accessorFn: (row) => row.last_seen_at ?? row.last_seen ?? row.updated_at ?? "",
      cell: ({ row }) => {
        const ts = row.original.last_seen_at ?? row.original.last_seen ?? row.original.updated_at;
        const status = lastSeenStatus(ts);
        return (
          <span className="inline-flex items-center gap-2" style={{ color: "var(--sx-muted)" }}>
            <span
              className={status === "online" ? "sx-live-dot" : ""}
              style={{ width: 8, height: 8, borderRadius: "50%", background: LAST_SEEN_DOT[status], display: "inline-block", flexShrink: 0 }}
            />
            {formatRelativeTime(ts)}
          </span>
        );
      },
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        const deviceId = getDeviceId(row.original);

        if (!deviceId) {
          return <span style={{ color: "var(--sx-dim)" }}>Unavailable</span>;
        }

        return (
          <Link to={`/devices/${encodeURIComponent(deviceId)}`} className="sx-button-secondary">
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