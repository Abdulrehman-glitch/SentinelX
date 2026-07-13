import { RefreshCw } from "lucide-react";
import type { HealthResponse, OverviewResponse } from "../types/api";

type Posture = {
  label: string;
  tone: "red" | "amber" | "green";
};

type DashStatusBarProps = {
  health: HealthResponse | null;
  overview: OverviewResponse | null;
  posture: Posture;
  isFetching: boolean;
  onRefresh: () => void;
};

export function DashStatusBar({
  health,
  overview,
  posture,
  isFetching,
  onRefresh,
}: DashStatusBarProps) {
  const postureColor =
    posture.tone === "red"
      ? "#e11d48"
      : posture.tone === "amber"
        ? "#c8102e"
        : "#22c55e";

  const postureShort =
    posture.tone === "red"
      ? "CRITICAL"
      : posture.tone === "amber"
        ? "WARNING"
        : "NOMINAL";

  const apiOk = health?.api_status === "online";
  const dbOk  = health?.database_status === "online";

  const unresolvedAlerts = overview?.alerts.unresolved ?? 0;
  const openIncidents    = overview?.incidents?.open ?? 0;

  return (
    <div
      className="flex h-[52px] shrink-0 items-center gap-5 border-b px-5"
      style={{
        background: "var(--sx-bg)",
        borderColor: "var(--sx-border)",
        fontFamily: "var(--font-mono)",
      }}
    >
      {/* Posture */}
      <div className="flex shrink-0 items-center gap-2">
        <span
          className="dc-dot-online inline-block h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ background: postureColor }}
          aria-hidden="true"
        />
        <span
          className="text-[10px] font-bold uppercase tracking-[0.22em]"
          style={{ color: postureColor }}
          aria-label={`System posture: ${postureShort}`}
        >
          {postureShort}
        </span>
      </div>

      <Divider />

      {/* Connectivity */}
      <div className="hidden items-center gap-3 sm:flex">
        <ServiceDot label="API" ok={apiOk} />
        <ServiceDot label="DB"  ok={dbOk}  />
      </div>

      <Divider className="hidden sm:block" />

      {/* Quick counts */}
      <div className="flex items-center gap-4">
        <QuickCount label="devices"   value={overview?.devices.total} />
        <QuickCount
          label="alerts"
          value={unresolvedAlerts}
          activeColor={unresolvedAlerts > 0 ? "#c8102e" : undefined}
        />
        <QuickCount
          label="incidents"
          value={openIncidents}
          activeColor={openIncidents > 0 ? "#e11d48" : undefined}
        />
      </div>

      <div className="flex-1" />

      {/* Service meta */}
      {health?.service && (
        <span
          className="hidden text-[10px] lg:block"
          style={{ color: "var(--sx-dim)" }}
        >
          {health.service}
          {health.version     ? ` v${health.version}`        : ""}
          {health.environment ? ` · ${health.environment}`   : ""}
        </span>
      )}

      {/* Refresh */}
      <button
        type="button"
        onClick={onRefresh}
        disabled={isFetching}
        aria-label="Refresh dashboard data"
        className="flex items-center gap-1.5 rounded border px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] transition disabled:cursor-not-allowed disabled:opacity-40"
        style={{
          borderColor: "var(--sx-border-md)",
          color: isFetching ? "var(--sx-accent)" : "var(--sx-muted)",
          background: "transparent",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--sx-text)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--sx-border-hi)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = isFetching ? "var(--sx-accent)" : "var(--sx-muted)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--sx-border-md)";
        }}
      >
        <RefreshCw
          size={10}
          strokeWidth={2.5}
          className={isFetching ? "animate-spin" : ""}
          aria-hidden="true"
        />
        {isFetching ? "Syncing" : "Sync"}
      </button>
    </div>
  );
}

function Divider({ className = "" }: { className?: string }) {
  return (
    <span
      className={`h-3.5 w-px shrink-0 ${className}`}
      style={{ background: "var(--sx-border-md)" }}
      aria-hidden="true"
    />
  );
}

function ServiceDot({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div
      className="flex items-center gap-1.5"
      aria-label={`${label}: ${ok ? "online" : "offline"}`}
    >
      <span
        className="inline-block h-1 w-1 rounded-full"
        style={{ background: ok ? "#22c55e" : "#e11d48" }}
        aria-hidden="true"
      />
      <span
        className="text-[10px] uppercase tracking-[0.14em]"
        style={{ color: "var(--sx-dim)" }}
      >
        {label}
      </span>
    </div>
  );
}

function QuickCount({
  label,
  value,
  activeColor,
}: {
  label: string;
  value: number | undefined;
  activeColor?: string;
}) {
  return (
    <span className="text-[10px]" style={{ color: "var(--sx-dim)" }}>
      <span
        className="font-bold tabular-nums"
        style={{ color: activeColor ?? "var(--sx-muted)" }}
      >
        {value ?? "—"}
      </span>{" "}
      {label}
    </span>
  );
}
