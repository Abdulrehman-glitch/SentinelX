import { Badge } from "./Badge";
import type { Device, OverviewResponse } from "../types/api";
import {
  getFleetAvailabilityPercent,
  getOfflineDeviceCount,
  getOnlineDeviceCount,
  getTotalDeviceCount,
} from "../utils/operations";

type FleetHealthPanelProps = {
  overview: OverviewResponse | null;
  devices: Device[];
};

export function FleetHealthPanel({ overview, devices }: FleetHealthPanelProps) {
  const total = getTotalDeviceCount(overview, devices);
  const online = getOnlineDeviceCount(overview, devices);
  const offline = getOfflineDeviceCount(overview, devices);
  const availability = getFleetAvailabilityPercent(overview, devices);

  const onlineWidth = total === 0 ? 0 : Math.round((online / total) * 100);
  const offlineWidth = total === 0 ? 0 : Math.round((offline / total) * 100);

  return (
    <section className="sx-panel rounded-2xl p-5 sx-animate-in sx-delay-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold sx-c-text">Fleet Health</h2>

          <p className="mt-1 text-sm sx-c-muted">
            Device availability and status distribution.
          </p>
        </div>

        <Badge
          tone={
            availability >= 80 ? "green" : availability >= 50 ? "amber" : "red"
          }
        >
          {`${availability}% online`}
        </Badge>
      </div>

      <div className="mt-6">
        <div className="flex h-3 overflow-hidden rounded-full sx-c-surface">
          <div
            className="bg-emerald-500 sx-bar-animated transition-[width]"
            style={{ width: `${onlineWidth}%` }}
          />
          <div
            className="bg-rose-500 transition-[width]"
            style={{ width: `${offlineWidth}%` }}
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-700/50 sx-c-surface p-4">
            <p className="text-sm sx-c-text0">Total</p>
            <p className="mt-1 text-2xl font-bold sx-c-text">{total}</p>
          </div>

          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/7 p-4">
            <p className="text-sm sx-c-success">Online</p>
            <p className="mt-1 text-2xl font-bold sx-c-success">{online}</p>
          </div>

          <div className="rounded-xl border border-rose-400/20 bg-rose-400/7 p-4">
            <p className="text-sm sx-c-danger">Offline</p>
            <p className="mt-1 text-2xl font-bold sx-c-danger">{offline}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
