import { ClipboardList, Shield } from "lucide-react";
import { Link } from "react-router";
import type { Alert, Device, Incident, OverviewResponse } from "../types/api";
import {
  getCriticalOpenAlerts,
  getFleetAvailabilityPercent,
  getOnlineDeviceCount,
  getTotalDeviceCount,
  getWarningOpenAlerts,
} from "../utils/operations";

type Posture = {
  label: string;
  tone: "red" | "amber" | "green";
  description: string;
};

type CommandStateProps = {
  overview: OverviewResponse | null;
  devices: Device[];
  alerts: Alert[];
  incidents: Incident[];
  posture: Posture;
};

function AvailabilityRing({ percent }: { percent: number }) {
  const SIZE   = 72;
  const STROKE = 4;
  const RADIUS = (SIZE - STROKE) / 2;
  const CIRC   = 2 * Math.PI * RADIUS;
  const clamped = Math.max(0, Math.min(100, percent));
  const offset  = CIRC * (1 - clamped / 100);

  const color =
    clamped >= 80 ? "#22c55e" : clamped >= 50 ? "#c8102e" : "#e11d48";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label={`Fleet availability: ${clamped}%`}
      >
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--sx-border-md)"
          strokeWidth={STROKE}
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={color}
          strokeWidth={STROKE}
          strokeDasharray={CIRC}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          className="dc-ring-progress"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="dc-mono text-base font-bold leading-none tabular-nums"
          style={{ color }}
          aria-hidden="true"
        >
          {clamped}
        </span>
        <span className="dc-mono text-[9px]" style={{ color: "var(--sx-dim)" }} aria-hidden="true">
          %
        </span>
      </div>
    </div>
  );
}

export function CommandState({
  overview,
  devices,
  alerts,
  incidents,
  posture,
}: CommandStateProps) {
  const critical = getCriticalOpenAlerts(alerts);
  const warning  = getWarningOpenAlerts(alerts);

  const openIncidents = incidents.filter(
    (i) => i.status?.toLowerCase() !== "resolved",
  );

  const totalDevices  = getTotalDeviceCount(overview, devices);
  const onlineDevices = getOnlineDeviceCount(overview, devices);
  const availability  = getFleetAvailabilityPercent(overview, devices);

  const postureColor =
    posture.tone === "red"
      ? "#e11d48"
      : posture.tone === "amber"
        ? "#c8102e"
        : "#22c55e";

  const postureWord =
    posture.tone === "red"
      ? "CRITICAL"
      : posture.tone === "amber"
        ? "WARNING"
        : "NOMINAL";

  return (
    <div className="flex h-full flex-col">
      {/* Panel header */}
      <div
        className="flex shrink-0 items-center gap-2 border-b px-4 py-3"
        style={{ borderColor: "var(--sx-border)" }}
      >
        <Shield size={11} strokeWidth={2} style={{ color: "var(--sx-dim)" }} aria-hidden="true" />
        <span className="dc-label">State</span>
      </div>

      <div className="overflow-y-auto lg:flex-1 lg:min-h-0">
        <div className="divide-y" style={{ borderColor: "var(--sx-border)" }}>

          {/* Posture */}
          <section className="px-4 py-4" aria-label="Operational posture">
            <p className="dc-label text-[9px]">Posture</p>
            <p
              className="dc-mono mt-2 text-lg font-bold uppercase leading-tight tracking-widest"
              style={{ color: postureColor }}
            >
              {postureWord}
            </p>
            <p className="mt-1 text-[10px] leading-4" style={{ color: "var(--sx-dim)" }}>
              {posture.description}
            </p>
          </section>

          {/* Fleet availability */}
          <section className="px-4 py-4" aria-label="Fleet availability">
            <p className="dc-label text-[9px]">Availability</p>
            <div className="mt-3 flex items-center gap-3">
              <AvailabilityRing percent={availability} />
              <div className="space-y-1">
                <p className="dc-mono text-[10px]" style={{ color: "var(--sx-muted)" }}>
                  <span className="font-semibold tabular-nums">{onlineDevices}</span>
                  {" / "}
                  <span className="font-semibold tabular-nums">{totalDevices}</span>
                  {" online"}
                </p>
              </div>
            </div>
          </section>

          {/* Alert queue */}
          <section className="px-4 py-4" aria-label="Alert queue">
            <div className="mb-3 flex items-center justify-between">
              <p className="dc-label text-[9px]">Alerts</p>
              <Link
                to="/alerts"
                className="dc-mono text-[9px] transition hover:text-slate-300"
                style={{ color: "var(--sx-dim)" }}
              >
                all →
              </Link>
            </div>
            <div className="space-y-2">
              <AlertRow color="#e11d48" label="Critical" count={critical.length} />
              <AlertRow color="#c8102e" label="Warning"  count={warning.length}  />
            </div>
          </section>

          {/* Open incidents */}
          <section className="px-4 py-4" aria-label="Open incidents">
            <div className="mb-3 flex items-center justify-between">
              <p className="dc-label text-[9px]">Incidents</p>
              <Link
                to="/incidents"
                className="dc-mono text-[9px] transition hover:text-slate-300"
                style={{ color: "var(--sx-dim)" }}
              >
                all →
              </Link>
            </div>

            {openIncidents.length === 0 ? (
              <p className="dc-mono text-[10px]" style={{ color: "var(--sx-dim)" }}>
                No open incidents.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {openIncidents.slice(0, 4).map((incident) => (
                  <li key={incident.id}>
                    <Link
                      to={`/incidents/${encodeURIComponent(incident.id)}`}
                      className="group flex items-start gap-2 rounded border px-2.5 py-2 transition"
                      style={{
                        borderColor: "rgba(244,63,94,0.14)",
                        background: "rgba(244,63,94,0.04)",
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLAnchorElement).style.background = "rgba(244,63,94,0.07)";
                        (e.currentTarget as HTMLAnchorElement).style.borderColor = "rgba(244,63,94,0.24)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLAnchorElement).style.background = "rgba(244,63,94,0.04)";
                        (e.currentTarget as HTMLAnchorElement).style.borderColor = "rgba(244,63,94,0.14)";
                      }}
                    >
                      <ClipboardList
                        size={10}
                        strokeWidth={2.5}
                        className="mt-px shrink-0"
                        style={{ color: "#e11d48" }}
                        aria-hidden="true"
                      />
                      <div className="min-w-0">
                        <p
                          className="truncate text-[10px] font-medium transition-colors group-hover:text-slate-200"
                          style={{ color: "var(--sx-muted)" }}
                        >
                          {incident.title}
                        </p>
                        <p
                          className="dc-mono text-[9px] uppercase tracking-wider"
                          style={{ color: "var(--sx-dim)" }}
                        >
                          {incident.severity}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Telemetry totals */}
          <section className="px-4 py-4" aria-label="Telemetry totals">
            <p className="dc-label text-[9px]">Telemetry</p>
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2.5">
              <TelemetryCell label="Metrics"          value={overview?.metrics?.total?.toLocaleString()} />
              <TelemetryCell label="Audit logs"       value={overview?.audit_logs?.total?.toLocaleString()} />
              <TelemetryCell
                label="Rules"
                value={
                  overview?.alert_rules
                    ? `${overview.alert_rules.enabled} / ${overview.alert_rules.total}`
                    : undefined
                }
              />
              <TelemetryCell label="Recovery actions" value={overview?.recovery_actions?.total?.toLocaleString()} />
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}

function AlertRow({ color, label, count }: { color: string; label: string; count: number }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-1 w-1 rounded-full"
          style={{ background: color }}
          aria-hidden="true"
        />
        <span className="dc-mono text-[10px]" style={{ color: "var(--sx-muted)" }}>
          {label}
        </span>
      </div>
      <span
        className="dc-mono text-sm font-bold tabular-nums"
        style={{ color: count > 0 ? color : "var(--sx-dim)" }}
        aria-label={`${count} ${label.toLowerCase()} alerts`}
      >
        {count}
      </span>
    </div>
  );
}

function TelemetryCell({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div>
      <dt className="dc-mono text-[9px]" style={{ color: "var(--sx-dim)" }}>{label}</dt>
      <dd className="dc-mono text-[11px] font-semibold" style={{ color: "var(--sx-muted)" }}>
        {value ?? "—"}
      </dd>
    </div>
  );
}
