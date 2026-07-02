import { FileDown, Printer, RefreshCw, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useAlertRulesQuery } from "../hooks/useAlertRulesQuery";
import { useAlertsQuery } from "../hooks/useAlertsQuery";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useDevicesQuery } from "../hooks/useDevicesQuery";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";
import { useOverviewQuery } from "../hooks/useOverviewQuery";
import { useRecoveryActionsQuery } from "../hooks/useRecoveryActionsQuery";
import { downloadCsv } from "../utils/csv";
import { formatRelativeTime } from "../utils/format";
import { Badge } from "./Badge";

type ReportType = "operational" | "fleet" | "incidents" | "compliance";
type Period = "24h" | "7d" | "30d" | "all";

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: "operational", label: "Operational overview" },
  { value: "fleet", label: "Fleet health" },
  { value: "incidents", label: "Alerts & incidents" },
  { value: "compliance", label: "Recovery & audit" },
];

const PERIODS: { value: Period; label: string }[] = [
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "all", label: "All time" },
];

function periodCutoff(period: Period): Date | null {
  if (period === "all") return null;
  const now = Date.now();
  const ms = period === "24h" ? 864e5 : period === "7d" ? 7 * 864e5 : 30 * 864e5;
  return new Date(now - ms);
}

function inPeriod(iso: string | null | undefined, cutoff: Date | null): boolean {
  if (!cutoff) return true;
  if (!iso) return false;
  const t = new Date(iso).getTime();
  return !Number.isNaN(t) && t >= cutoff.getTime();
}

function isUnresolvedAlert(a: { resolved?: boolean; is_resolved?: boolean }) {
  return !(a.resolved ?? a.is_resolved ?? false);
}

export function ExecutiveReport() {
  const { user } = useAuth();
  const overviewQuery = useOverviewQuery();
  const devicesQuery = useDevicesQuery();
  const alertsQuery = useAlertsQuery();
  const incidentsQuery = useIncidentsQuery();
  const recoveryQuery = useRecoveryActionsQuery();
  const rulesQuery = useAlertRulesQuery();
  const auditQuery = useAuditLogsQuery();

  const [reportType, setReportType] = useState<ReportType>("operational");
  const [period, setPeriod] = useState<Period>("30d");
  const [generatedAt, setGeneratedAt] = useState(() => new Date());

  const cutoff = useMemo(() => periodCutoff(period), [period]);

  const r = useMemo(() => {
    const devices = devicesQuery.data ?? [];
    const alerts = (alertsQuery.data ?? []).filter((a) => inPeriod(a.created_at, cutoff));
    const incidents = (incidentsQuery.data ?? []).filter((i) => inPeriod(i.created_at, cutoff));
    const recovery = (recoveryQuery.data ?? []).filter((x) => inPeriod(x.created_at, cutoff));
    const rules = rulesQuery.data ?? [];
    const audit = (auditQuery.data ?? []).filter((a) => inPeriod(a.created_at, cutoff));

    const online = devices.filter((d) => d.status?.toLowerCase() === "online").length;
    const offline = devices.filter((d) => d.status?.toLowerCase() === "offline").length;
    const criticalAlerts = alerts.filter((a) => a.severity === "critical").length;
    const warningAlerts = alerts.filter((a) => a.severity === "warning").length;
    const unresolvedAlerts = alerts.filter(isUnresolvedAlert).length;
    const openIncidents = incidents.filter((i) => i.status === "open" || i.status === "investigating").length;
    const resolvedIncidents = incidents.filter((i) => i.status === "resolved").length;
    const enabledRules = rules.filter((x) => x.enabled).length;

    return {
      devices,
      alerts,
      incidents,
      recovery,
      audit,
      devicesTotal: devices.length,
      online,
      offline,
      criticalAlerts,
      warningAlerts,
      unresolvedAlerts,
      alertsTotal: alerts.length,
      openIncidents,
      resolvedIncidents,
      recoveryTotal: recovery.length,
      rulesEnabled: enabledRules,
      rulesTotal: rules.length,
      auditTotal: audit.length,
    };
  }, [
    devicesQuery.data, alertsQuery.data, incidentsQuery.data,
    recoveryQuery.data, rulesQuery.data, auditQuery.data, cutoff,
  ]);

  const verdict: { level: "critical" | "elevated" | "stable"; label: string; note: string } =
    r.criticalAlerts > 0 || r.openIncidents > 2
      ? { level: "critical", label: "Action required", note: "Critical alerts or multiple open incidents demand immediate attention." }
      : r.unresolvedAlerts > 0 || r.openIncidents > 0 || r.offline > 0
        ? { level: "elevated", label: "Monitoring", note: "Unresolved conditions are present and should be reviewed this period." }
        : { level: "stable", label: "Operational", note: "No unresolved alerts or open incidents in the selected period." };

  const periodLabel = PERIODS.find((p) => p.value === period)?.label ?? "";
  const typeLabel = REPORT_TYPES.find((t) => t.value === reportType)?.label ?? "";

  function regenerate() {
    setGeneratedAt(new Date());
    void Promise.all([
      overviewQuery.refetch(), devicesQuery.refetch(), alertsQuery.refetch(),
      incidentsQuery.refetch(), recoveryQuery.refetch(), rulesQuery.refetch(), auditQuery.refetch(),
    ]);
  }

  function exportCsv() {
    downloadCsv(`sentinelx-${reportType}-report.csv`, [
      {
        report_type: typeLabel,
        period: periodLabel,
        generated_at: generatedAt.toISOString(),
        devices_total: r.devicesTotal,
        devices_online: r.online,
        devices_offline: r.offline,
        alerts_total: r.alertsTotal,
        alerts_critical: r.criticalAlerts,
        alerts_warning: r.warningAlerts,
        alerts_unresolved: r.unresolvedAlerts,
        incidents_open: r.openIncidents,
        incidents_resolved: r.resolvedIncidents,
        recovery_actions: r.recoveryTotal,
        alert_rules_enabled: r.rulesEnabled,
        audit_events: r.auditTotal,
        verdict: verdict.label,
      },
    ]);
  }

  const showFleet = reportType === "operational" || reportType === "fleet";
  const showIncidents = reportType === "operational" || reportType === "incidents";
  const showCompliance = reportType === "operational" || reportType === "compliance";

  return (
    <div className="mt-6">
      {/* Controls */}
      <section className="sx-panel mb-6 p-5" style={{ borderRadius: "16px" }}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="sx-field-label" htmlFor="rpt-type">Report type</label>
              <select id="rpt-type" className="sx-select mt-1.5" style={{ minWidth: 200 }}
                value={reportType} onChange={(e) => setReportType(e.target.value as ReportType)}>
                {REPORT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="sx-field-label" htmlFor="rpt-period">Reporting period</label>
              <select id="rpt-period" className="sx-select mt-1.5" style={{ minWidth: 170 }}
                value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
                {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={regenerate} className="sx-button-secondary">
              <RefreshCw size={15} /> Generate
            </button>
            <button type="button" onClick={exportCsv} className="sx-button-secondary">
              <FileDown size={15} /> Export CSV
            </button>
            <button type="button" onClick={() => window.print()} className="sx-button-primary">
              <Printer size={15} /> Print / PDF
            </button>
          </div>
        </div>
      </section>

      {/* Report document */}
      <article className="sx-panel p-0" style={{ borderRadius: "16px", overflow: "hidden" }}>
        {/* Letterhead */}
        <header
          className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between"
          style={{ borderBottom: "1px solid var(--sx-border)", background: "var(--sx-panel-2)" }}
        >
          <div className="flex items-center gap-3">
            <div className="sx-topbar-badge" style={{ width: 40, height: 40, fontSize: 13, borderRadius: 11 }}>SX</div>
            <div>
              <h2 className="text-lg font-extrabold" style={{ color: "var(--sx-text)", letterSpacing: "-0.02em" }}>
                SentinelX {typeLabel} Report
              </h2>
              <p className="text-xs" style={{ color: "var(--sx-muted)", fontFamily: "var(--font-mono)" }}>
                {periodLabel} · Generated {generatedAt.toLocaleString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs" style={{ color: "var(--sx-dim)" }}>Prepared for</p>
              <p className="text-sm font-semibold" style={{ color: "var(--sx-text)" }}>
                {user?.full_name ?? "Operator"} · <span style={{ textTransform: "capitalize" }}>{user?.role ?? "viewer"}</span>
              </p>
            </div>
            <Badge tone={verdict.level === "critical" ? "red" : verdict.level === "elevated" ? "amber" : "green"}>
              {verdict.label}
            </Badge>
          </div>
        </header>

        {/* Executive verdict */}
        <section className="p-6" style={{ borderBottom: "1px solid var(--sx-border)" }}>
          <div className="flex items-start gap-3">
            <ShieldCheck size={18} className="mt-0.5 shrink-0" style={{ color: "var(--sx-accent-text)" }} />
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: "var(--sx-muted)" }}>Executive summary</h3>
              <p className="mt-1.5 text-sm leading-6" style={{ color: "var(--sx-text)" }}>
                Over the {periodLabel.toLowerCase()}, SentinelX monitored{" "}
                <strong>{r.devicesTotal}</strong> device{r.devicesTotal === 1 ? "" : "s"} ({r.online} online, {r.offline} offline),
                generating <strong>{r.alertsTotal}</strong> alert{r.alertsTotal === 1 ? "" : "s"}{" "}
                (<strong>{r.criticalAlerts}</strong> critical) and <strong>{r.openIncidents}</strong> open incident{r.openIncidents === 1 ? "" : "s"}.
                Status: <strong>{verdict.label}</strong> — {verdict.note}
              </p>
            </div>
          </div>
        </section>

        {/* KPI grid */}
        <section className="grid gap-px p-6 sm:grid-cols-2 xl:grid-cols-4" style={{ background: "var(--sx-border)" }}>
          {[
            { label: "Fleet size", value: r.devicesTotal, sub: `${r.online} online · ${r.offline} offline`, tone: "var(--sx-text)" },
            { label: "Unresolved alerts", value: r.unresolvedAlerts, sub: `${r.criticalAlerts} critical · ${r.warningAlerts} warning`, tone: r.unresolvedAlerts ? "var(--sx-amber)" : "var(--sx-green)" },
            { label: "Open incidents", value: r.openIncidents, sub: `${r.resolvedIncidents} resolved this period`, tone: r.openIncidents ? "var(--sx-red)" : "var(--sx-green)" },
            { label: "Recovery actions", value: r.recoveryTotal, sub: `${r.rulesEnabled}/${r.rulesTotal} alert rules active`, tone: "var(--sx-text)" },
          ].map((kpi) => (
            <div key={kpi.label} className="p-4" style={{ background: "var(--sx-panel)" }}>
              <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--sx-muted)" }}>{kpi.label}</p>
              <p className="mt-2 text-3xl font-extrabold tabular-nums" style={{ color: kpi.tone, letterSpacing: "-0.02em" }}>{kpi.value}</p>
              <p className="mt-1 text-xs" style={{ color: "var(--sx-dim)" }}>{kpi.sub}</p>
            </div>
          ))}
        </section>

        {/* Fleet section */}
        {showFleet && (
          <ReportSection title="Fleet status" subtitle="Registered devices and their current state.">
            {r.devices.length === 0 ? (
              <EmptyRow text="No devices registered in this organization." />
            ) : (
              <ReportTable
                head={["Device", "Status", "IP address", "Last seen"]}
                rows={r.devices.slice(0, 12).map((d) => [
                  d.display_name ? `${d.display_name}` : d.hostname,
                  <Badge key="s" tone={d.status?.toLowerCase() === "online" ? "green" : d.status?.toLowerCase() === "offline" ? "red" : "slate"}>{d.status ?? "unknown"}</Badge>,
                  d.ip_address ?? "—",
                  formatRelativeTime(d.last_seen_at ?? d.last_seen ?? d.updated_at),
                ])}
              />
            )}
          </ReportSection>
        )}

        {/* Alerts & incidents section */}
        {showIncidents && (
          <ReportSection title="Alerts & incidents" subtitle={`Severity breakdown for ${periodLabel.toLowerCase()}.`}>
            <div className="mb-4 flex flex-wrap gap-2">
              <Chip tone="red" label={`${r.criticalAlerts} critical`} />
              <Chip tone="amber" label={`${r.warningAlerts} warning`} />
              <Chip tone="slate" label={`${r.unresolvedAlerts} unresolved`} />
              <Chip tone="blue" label={`${r.openIncidents} open incidents`} />
            </div>
            {r.incidents.length === 0 ? (
              <EmptyRow text="No incidents recorded in this period." />
            ) : (
              <ReportTable
                head={["Incident", "Severity", "Status", "Opened"]}
                rows={r.incidents.slice(0, 10).map((i) => [
                  i.title ?? "Incident",
                  <Badge key="s" tone={i.severity === "critical" ? "red" : i.severity === "warning" ? "amber" : "slate"}>{i.severity ?? "info"}</Badge>,
                  i.status ?? "open",
                  formatRelativeTime(i.created_at),
                ])}
              />
            )}
          </ReportSection>
        )}

        {/* Recovery & audit section */}
        {showCompliance && (
          <ReportSection title="Recovery & audit trail" subtitle="Recovery actions and governance evidence.">
            <div className="mb-4 flex flex-wrap gap-2">
              <Chip tone="green" label={`${r.recoveryTotal} recovery actions`} />
              <Chip tone="slate" label={`${r.auditTotal} audit events`} />
              <Chip tone="blue" label={`${r.rulesEnabled} active rules`} />
            </div>
            {r.recovery.length === 0 ? (
              <EmptyRow text="No recovery actions logged in this period." />
            ) : (
              <ReportTable
                head={["Action", "Status", "Logged"]}
                rows={r.recovery.slice(0, 10).map((x) => [
                  x.action_type ?? "recovery_action",
                  x.status ?? "logged",
                  formatRelativeTime(x.created_at),
                ])}
              />
            )}
          </ReportSection>
        )}

        <footer className="p-5 text-center" style={{ borderTop: "1px solid var(--sx-border)" }}>
          <p className="text-xs" style={{ color: "var(--sx-dim)", fontFamily: "var(--font-mono)" }}>
            CONFIDENTIAL · Generated by SentinelX Operations Console · {generatedAt.toLocaleString()}
          </p>
        </footer>
      </article>
    </div>
  );
}

function ReportSection({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="p-6" style={{ borderBottom: "1px solid var(--sx-border)" }}>
      <h3 className="text-base font-bold" style={{ color: "var(--sx-text)" }}>{title}</h3>
      <p className="mb-4 mt-0.5 text-sm" style={{ color: "var(--sx-muted)" }}>{subtitle}</p>
      {children}
    </section>
  );
}

function ReportTable({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid var(--sx-border)" }}>
      <table className="min-w-full">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-[0.16em]"
                style={{ color: "var(--sx-dim)", fontFamily: "var(--font-mono)", background: "var(--sx-panel-2)", borderBottom: "1px solid var(--sx-border)" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, ri) => (
            <tr key={ri} style={{ borderBottom: ri < rows.length - 1 ? "1px solid var(--sx-border)" : "none" }}>
              {cells.map((c, ci) => (
                <td key={ci} className="px-4 py-2.5 text-sm" style={{ color: "var(--sx-text)" }}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Chip({ tone, label }: { tone: "red" | "amber" | "green" | "blue" | "slate"; label: string }) {
  return <Badge tone={tone}>{label}</Badge>;
}

function EmptyRow({ text }: { text: string }) {
  return <p className="rounded-xl px-4 py-6 text-sm" style={{ color: "var(--sx-muted)", background: "var(--sx-panel-2)", border: "1px solid var(--sx-border)" }}>{text}</p>;
}
