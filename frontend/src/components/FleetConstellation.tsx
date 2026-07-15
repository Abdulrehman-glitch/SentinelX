import { ChevronRight, Server } from "lucide-react";
import { Link } from "react-router";
import type { Alert, Device } from "../types/api";
import { relativeTime } from "../utils/dashboard";
import { getCriticalOpenAlerts, getDeviceId } from "../utils/operations";

type FleetConstellationProps = {
  devices: Device[];
  alerts: Alert[];
  isLoading: boolean;
};

type DeviceStatus = "online" | "offline" | "warning" | "unknown";

function resolveStatus(device: Device): DeviceStatus {
  const s = device.status?.toLowerCase();
  if (s === "online")  return "online";
  if (s === "offline") return "offline";
  if (s === "warning") return "warning";
  return "unknown";
}

function StatusDot({ status, critical }: { status: DeviceStatus; critical: boolean }) {
  if (critical) {
    return (
      <span
        className="dc-dot-critical inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: "var(--sx-red)" }}
        role="img"
        aria-label="Critical alert"
      />
    );
  }
  if (status === "online") {
    return (
      <span
        className="dc-dot-online inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: "var(--sx-green)" }}
        role="img"
        aria-label="Online"
      />
    );
  }
  if (status === "warning") {
    return (
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: "var(--sx-amber)" }}
        role="img"
        aria-label="Warning"
      />
    );
  }
  return (
    <span
      className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
      style={{ background: "var(--sx-dim)", border: "1px solid var(--sx-border-md)" }}
      role="img"
      aria-label="Offline"
    />
  );
}

function DeviceRow({
  device,
  hasCriticalAlert,
}: {
  device: Device;
  hasCriticalAlert: boolean;
}) {
  const deviceId = getDeviceId(device);
  const status   = resolveStatus(device);
  const lastSeen = device.last_seen ?? device.updated_at ?? null;

  return (
    <Link
      to={`/devices/${encodeURIComponent(deviceId)}`}
      className="dc-device-row group flex items-center gap-3 px-5 py-3 focus-visible:outline-none"
      aria-label={`Open device ${device.hostname}`}
    >
      <StatusDot status={status} critical={hasCriticalAlert} />

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p
            className="dc-mono truncate text-[13px] font-medium transition-colors group-hover:text-slate-100"
            style={{ color: "var(--sx-muted)" }}
          >
            {device.hostname}
          </p>
          {device.os_name && (
            <p
              className="dc-mono hidden shrink-0 truncate text-[10px] sm:block"
              style={{ color: "var(--sx-dim)" }}
            >
              {device.os_name}
            </p>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-1.5">
          <p className="dc-mono text-[10px]" style={{ color: "var(--sx-dim)" }}>
            {device.ip_address ?? "—"}
          </p>
          {lastSeen && (
            <>
              <span className="text-[10px]" style={{ color: "var(--sx-dim)" }} aria-hidden="true">·</span>
              <p className="dc-mono text-[10px]" style={{ color: "var(--sx-dim)" }}>
                {relativeTime(lastSeen)}
              </p>
            </>
          )}
        </div>
      </div>

      <ChevronRight
        size={11}
        strokeWidth={2.5}
        className="shrink-0 transition-colors group-hover:text-slate-400"
        style={{ color: "var(--sx-dim)" }}
        aria-hidden="true"
      />
    </Link>
  );
}

function Skeleton() {
  return (
    <div className="space-y-px" aria-busy="true" aria-label="Loading devices">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-5 py-3">
          <div
            className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full"
            style={{ background: "var(--sx-dim)" }}
          />
          <div className="flex-1 space-y-1.5">
            <div
              className="h-2.5 animate-pulse rounded"
              style={{
                width: `${72 + (i % 3) * 20}px`,
                background: "var(--sx-dim)",
                animationDelay: `${i * 0.06}s`,
                opacity: 0.4,
              }}
            />
            <div
              className="h-2 w-20 animate-pulse rounded"
              style={{ background: "var(--sx-dim)", opacity: 0.2 }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function FleetConstellation({
  devices,
  alerts,
  isLoading,
}: FleetConstellationProps) {
  const onlineCount  = devices.filter((d) => d.status?.toLowerCase() === "online").length;
  const offlineCount = devices.filter((d) => d.status?.toLowerCase() === "offline").length;

  const criticalDeviceIds = new Set(
    getCriticalOpenAlerts(alerts)
      .map((a) => a.device_id)
      .filter((id): id is string => !!id),
  );

  return (
    <div className="flex h-full flex-col">
      {/* Panel header */}
      <div
        className="flex shrink-0 items-center justify-between border-b px-5 py-3"
        style={{ borderColor: "var(--sx-border)" }}
      >
        <div className="flex items-center gap-2">
          <Server size={11} strokeWidth={2} style={{ color: "var(--sx-dim)" }} aria-hidden="true" />
          <span className="dc-label">Fleet</span>
        </div>
        <div className="flex items-center gap-3">
          {onlineCount > 0 && (
            <span className="dc-mono text-[10px] font-semibold" style={{ color: "var(--sx-green)" }}>
              {onlineCount} online
            </span>
          )}
          {offlineCount > 0 && (
            <span className="dc-mono text-[10px] font-semibold" style={{ color: "var(--sx-red)" }}>
              {offlineCount} offline
            </span>
          )}
          <span className="dc-mono text-[10px]" style={{ color: "var(--sx-dim)" }}>
            {devices.length} total
          </span>
        </div>
      </div>

      {/* Device list */}
      <div
        className="overflow-y-auto lg:flex-1 lg:min-h-0"
        role="list"
        aria-label="Registered devices"
      >
        {isLoading && devices.length === 0 ? (
          <Skeleton />
        ) : devices.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <Server size={20} strokeWidth={1.5} style={{ color: "var(--sx-dim)" }} aria-hidden="true" />
            <p className="dc-mono mt-3 text-xs" style={{ color: "var(--sx-dim)" }}>
              No devices registered.
            </p>
            <p className="mt-1 text-[11px] leading-5" style={{ color: "var(--sx-dim)", opacity: 0.7 }}>
              Start the monitoring agent to register a device.
            </p>
          </div>
        ) : (
          devices.map((device) => {
            const id = getDeviceId(device);
            return (
              <DeviceRow
                key={id || device.hostname}
                device={device}
                hasCriticalAlert={criticalDeviceIds.has(id)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
