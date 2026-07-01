import { Badge } from "./Badge";
import type {
  Alert,
  Device,
  OverviewResponse,
  RecoveryAction,
} from "../types/api";
import {
  getCriticalOpenAlerts,
  getFleetAvailabilityPercent,
  getOpenAlerts,
  getOperationalPosture,
  getWarningOpenAlerts,
} from "../utils/operations";

type OperationsSnapshotProps = {
  overview: OverviewResponse | null;
  devices: Device[];
  alerts: Alert[];
  recoveryActions: RecoveryAction[];
};

export function OperationsSnapshot({
  overview,
  devices,
  alerts,
  recoveryActions,
}: OperationsSnapshotProps) {
  const posture = getOperationalPosture(overview, devices, alerts);
  const availability = getFleetAvailabilityPercent(overview, devices);
  const openAlerts = getOpenAlerts(alerts);
  const criticalAlerts = getCriticalOpenAlerts(alerts);
  const warningAlerts = getWarningOpenAlerts(alerts);

  const availabilityColor =
    availability >= 80
      ? "text-emerald-300"
      : availability >= 50
        ? "text-violet-300"
        : "text-rose-300";

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5 sx-animate-in sx-delay-3">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
            Operations Snapshot
          </p>

          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
            <h2 className="text-2xl font-bold tracking-tight text-slate-50">
              {posture.label}
            </h2>

            <Badge tone={posture.tone}>{posture.tone}</Badge>
          </div>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            {posture.description}
          </p>
        </div>

        <div className="shrink-0 rounded-2xl border border-slate-700/60 bg-slate-900/60 px-5 py-4">
          <p className="text-sm font-medium text-slate-500">Fleet availability</p>
          <p className={`mt-2 text-4xl font-bold tracking-tight ${availabilityColor}`}>
            {availability}%
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-4">
          <p className="text-sm font-medium text-slate-500">Open alerts</p>
          <p className="mt-2 text-2xl font-bold text-slate-100">
            {openAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-rose-400/25 bg-rose-400/8 p-4">
          <p className="text-sm font-medium text-rose-400/80">Critical alerts</p>
          <p className="mt-2 text-2xl font-bold text-rose-300">
            {criticalAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-violet-500/25 bg-violet-500/10 p-4">
          <p className="text-sm font-medium text-violet-400/80">Warning alerts</p>
          <p className="mt-2 text-2xl font-bold text-violet-300">
            {warningAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/7 p-4">
          <p className="text-sm font-medium text-emerald-400/80">Recovery actions</p>
          <p className="mt-2 text-2xl font-bold text-emerald-300">
            {recoveryActions.length}
          </p>
        </div>
      </div>
    </section>
  );
}
