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
      ? "sx-c-success"
      : availability >= 50
        ? "sx-c-accent"
        : "sx-c-danger";

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5 sx-animate-in sx-delay-3">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.25em] sx-c-text0">
            Operations Snapshot
          </p>

          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
            <h2 className="text-2xl font-bold tracking-tight sx-c-text">
              {posture.label}
            </h2>

            <Badge tone={posture.tone}>{posture.tone}</Badge>
          </div>

          <p className="mt-2 max-w-3xl text-sm leading-6 sx-c-muted">
            {posture.description}
          </p>
        </div>

        <div className="shrink-0 rounded-2xl border border-slate-700/60 sx-c-surface px-5 py-4">
          <p className="text-sm font-medium sx-c-text0">Fleet availability</p>
          <p className={`mt-2 text-4xl font-bold tracking-tight ${availabilityColor}`}>
            {availability}%
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-slate-700/50 sx-c-surface p-4">
          <p className="text-sm font-medium sx-c-text0">Open alerts</p>
          <p className="mt-2 text-2xl font-bold sx-c-text">
            {openAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-rose-400/25 bg-rose-400/8 p-4">
          <p className="text-sm font-medium sx-c-danger">Critical alerts</p>
          <p className="mt-2 text-2xl font-bold sx-c-danger">
            {criticalAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-violet-500/25 bg-violet-500/10 p-4">
          <p className="text-sm font-medium sx-c-accent">Warning alerts</p>
          <p className="mt-2 text-2xl font-bold sx-c-accent">
            {warningAlerts.length}
          </p>
        </div>

        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/7 p-4">
          <p className="text-sm font-medium sx-c-success">Recovery actions</p>
          <p className="mt-2 text-2xl font-bold sx-c-success">
            {recoveryActions.length}
          </p>
        </div>
      </div>
    </section>
  );
}
