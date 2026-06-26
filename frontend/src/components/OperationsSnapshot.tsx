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

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
            Operations Snapshot
          </p>

          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
            <h2 className="text-2xl font-bold tracking-tight text-slate-950">
              {posture.label}
            </h2>

            <Badge tone={posture.tone}>{posture.tone}</Badge>
          </div>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {posture.description}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4">
          <p className="text-sm font-medium text-slate-500">
            Fleet availability
          </p>

          <p className="mt-2 text-4xl font-bold tracking-tight text-slate-950">
            {availability}%
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-500">Open alerts</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">
            {openAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <p className="text-sm font-medium text-rose-600">Critical alerts</p>
          <p className="mt-2 text-2xl font-bold text-rose-900">
            {criticalAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-700">Warning alerts</p>
          <p className="mt-2 text-2xl font-bold text-amber-900">
            {warningAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-medium text-emerald-700">
            Recovery actions
          </p>
          <p className="mt-2 text-2xl font-bold text-emerald-900">
            {recoveryActions.length}
          </p>
        </div>
      </div>
    </section>
  );
}