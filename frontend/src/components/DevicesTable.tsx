import type { Device } from "../types/api";

type DevicesTableProps = {
  devices: Device[];
};

function formatDate(value?: string | null) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function getStatusClasses(status?: string) {
  const normalisedStatus = status?.toLowerCase();

  if (normalisedStatus === "online") {
    return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
  }

  if (normalisedStatus === "offline") {
    return "bg-rose-50 text-rose-700 ring-1 ring-rose-200";
  }

  return "bg-slate-100 text-slate-700 ring-1 ring-slate-200";
}

export function DevicesTable({ devices }: DevicesTableProps) {
  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-950">
          Registered Devices
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Monitored machines and agents registered with the SentinelX backend.
        </p>
      </div>

      {devices.length === 0 ? (
        <div className="px-5 py-8 text-sm text-slate-500">
          No devices have been registered yet. Start the SentinelX agent or
          register a device through the API.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Hostname
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  IP Address
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Operating System
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Status
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Last Seen
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 bg-white">
              {devices.map((device, index) => {
                const key =
                  device.id ??
                  device.device_id ??
                  `${device.hostname}-${device.ip_address}-${index}`;

                return (
                  <tr key={key} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-5 py-4 text-sm font-medium text-slate-950">
                      {device.hostname}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">
                      {device.ip_address}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">
                      {device.os_name}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${getStatusClasses(
                          device.status,
                        )}`}
                      >
                        {device.status ?? "unknown"}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-sm text-slate-600">
                      {formatDate(device.last_seen ?? device.updated_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}