import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { Plus } from "lucide-react";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useDashboardData } from "../hooks/useDashboardData";
import { useDeviceLatestMetricsQuery } from "../hooks/useDeviceLatestMetricsQuery";
import { useIncidentsQuery } from "../hooks/useIncidentsQuery";
import type { Alert, Device } from "../types/api";
import { buildEventStream, relativeTime } from "../utils/dashboard";
import {
  getCriticalOpenAlerts,
  getDeviceId,
  getOfflineDeviceCount,
  getOnlineDeviceCount,
  getOpenAlerts,
  getWarningOpenAlerts,
} from "../utils/operations";

/**
 * Sentinel Command — the authenticated home. Everything rendered here is real
 * state: posture derives from live alerts/devices, the Core shows enrolled
 * devices with their latest telemetry, and the NOW stream is the actual
 * alert/recovery/audit history. Loading states animate; values never lie.
 */
export function SentinelCommandPage() {
  const { overview, devices, alerts, recoveryActions, isLoading } = useDashboardData();
  const incidentsQuery = useIncidentsQuery();
  const auditLogsQuery = useAuditLogsQuery();

  const [introDone, setIntroDone] = useState(
    () => sessionStorage.getItem("sx-command-intro") === "done",
  );
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (introDone) return;
    if (reducedMotion) {
      sessionStorage.setItem("sx-command-intro", "done");
      setIntroDone(true);
      return;
    }
    const t = window.setTimeout(() => {
      sessionStorage.setItem("sx-command-intro", "done");
      setIntroDone(true);
    }, 1900);
    return () => window.clearTimeout(t);
  }, [introDone, reducedMotion]);

  const openAlerts = getOpenAlerts(alerts);
  const critical = getCriticalOpenAlerts(alerts).length;
  const warnings = getWarningOpenAlerts(alerts).length;
  const offline = getOfflineDeviceCount(overview, devices);
  const online = getOnlineDeviceCount(overview, devices);
  const attention = critical + offline;

  const headline = isLoading
    ? "ESTABLISHING OPERATIONAL PICTURE"
    : attention > 0
      ? `${attention} SYSTEM${attention === 1 ? "" : "S"} REQUIRE${attention === 1 ? "S" : ""} ATTENTION`
      : warnings > 0
        ? `${warnings} WARNING${warnings === 1 ? "" : "S"} ACTIVE`
        : "ALL SYSTEMS NOMINAL";

  const headlineTone = isLoading
    ? "var(--cmd-dim)"
    : attention > 0
      ? "var(--cmd-red)"
      : warnings > 0
        ? "var(--cmd-amber)"
        : "var(--cmd-green)";

  const subline = isLoading
    ? " "
    : `${online} agent${online === 1 ? "" : "s"} connected${online > 0 ? " · telemetry live" : ""}`;

  const streamEvents = useMemo(
    () => buildEventStream(alerts, recoveryActions, auditLogsQuery.data ?? [], 12),
    [alerts, recoveryActions, auditLogsQuery.data],
  );

  const timelineEvents = useMemo(
    () => buildEventStream(alerts, recoveryActions, auditLogsQuery.data ?? [], 30),
    [alerts, recoveryActions, auditLogsQuery.data],
  );

  return (
    <div className="cmd-root">
      <CommandBackdrop reducedMotion={reducedMotion} />

      {!introDone && (
        <div className="cmd-intro" aria-hidden>
          <p className="cmd-intro-word">SENTINELX</p>
          <p className="cmd-intro-tag">Detect. Defend. Recover.</p>
          <p className="cmd-intro-sub">Establishing operational picture…</p>
        </div>
      )}

      <div className={`cmd-content ${introDone ? "cmd-content-visible" : ""}`}>
        {/* Hero */}
        <section className="cmd-hero">
          <p className="cmd-eyebrow">SENTINEL COMMAND</p>
          <h1 className="cmd-headline" style={{ color: headlineTone }}>
            {headline}
          </h1>
          <p className="cmd-subline">{subline}</p>
        </section>

        {/* Sentinel Core */}
        <section className="cmd-core-section" aria-label="Sentinel Core — monitored devices">
          <SentinelCore devices={devices} alerts={openAlerts} isLoading={isLoading} />
        </section>

        {/* NOW stream + posture detail */}
        <section className="cmd-lower">
          <div className="cmd-now sx-reveal">
            <h2 className="cmd-panel-title">NOW</h2>
            {streamEvents.length === 0 ? (
              <p className="cmd-quiet">Quiet. Nothing has happened recently.</p>
            ) : (
              <ul className="cmd-now-list">
                {streamEvents.map((e) => (
                  <li key={e.key}>
                    <Link to={e.href} className="cmd-now-row">
                      <span className="cmd-now-time">{shortTime(e.timestamp)}</span>
                      <span className={`cmd-now-dot cmd-sev-${e.severity}`} aria-hidden />
                      <span className="cmd-now-text">{e.headline}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="cmd-posture sx-reveal">
            <h2 className="cmd-panel-title">POSTURE</h2>
            <dl className="cmd-posture-grid">
              <PostureStat label="Agents online" value={isLoading ? "—" : String(online)} />
              <PostureStat label="Offline" value={isLoading ? "—" : String(offline)} tone={offline > 0 ? "red" : undefined} />
              <PostureStat label="Open alerts" value={isLoading ? "—" : String(openAlerts.length)} tone={critical > 0 ? "red" : warnings > 0 ? "amber" : undefined} />
              <PostureStat
                label="Open incidents"
                value={
                  incidentsQuery.isLoading
                    ? "—"
                    : String((incidentsQuery.data ?? []).filter((i) => i.status !== "resolved" && i.status !== "closed").length)
                }
              />
            </dl>
            <div className="cmd-posture-links">
              <Link to="/devices" className="cmd-link">Fleet</Link>
              <Link to="/alerts" className="cmd-link">Alerts</Link>
              <Link to="/incidents" className="cmd-link">Incidents</Link>
              <Link to="/console" className="cmd-link">Ops console</Link>
            </div>
          </div>
        </section>

        {/* Pulse timeline */}
        <section className="cmd-timeline-section sx-reveal" aria-label="Recent operational activity">
          <h2 className="cmd-panel-title">SYSTEM PULSE</h2>
          {timelineEvents.length === 0 ? (
            <p className="cmd-quiet">No recorded activity in this window.</p>
          ) : (
            <ol className="cmd-timeline">
              {timelineEvents.map((e) => (
                <li key={e.key} className="cmd-timeline-item">
                  <span className={`cmd-timeline-marker cmd-sev-${e.severity}`} aria-hidden />
                  <div className="cmd-timeline-body">
                    <Link to={e.href} className="cmd-timeline-headline">{e.headline}</Link>
                    {e.detail && <p className="cmd-timeline-detail">{e.detail}</p>}
                    <p className="cmd-timeline-time">{relativeTime(e.timestamp)}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}

function PostureStat({ label, value, tone }: { label: string; value: string; tone?: "red" | "amber" }) {
  return (
    <div className="cmd-stat">
      <dt className="cmd-stat-label">{label}</dt>
      <dd
        className="cmd-stat-value"
        style={tone === "red" ? { color: "var(--cmd-red)" } : tone === "amber" ? { color: "var(--cmd-amber)" } : undefined}
      >
        {value}
      </dd>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sentinel Core                                                       */
/* ------------------------------------------------------------------ */

function SentinelCore({ devices, alerts, isLoading }: {
  devices: Device[];
  alerts: Alert[];
  isLoading: boolean;
}) {
  // Split enrolled devices around the core: first half above, rest below.
  const shown = devices.slice(0, 6);
  const half = Math.ceil(shown.length / 2);
  const top = shown.slice(0, half);
  const bottom = shown.slice(half);

  return (
    <div className="cmd-core">
      <div className="cmd-core-row">
        {top.map((d) => (
          <DeviceNode key={getDeviceId(d)} device={d} alerts={alerts} position="top" />
        ))}
        {!isLoading && shown.length === 0 && (
          <div className="cmd-node cmd-node-empty">
            <p className="cmd-node-name">No agents yet</p>
            <p className="cmd-node-meta">Pair a device to begin</p>
          </div>
        )}
      </div>

      <div className="cmd-core-hub" aria-hidden>
        <span className="cmd-core-ring" />
        <span className="cmd-core-mark">SENTINEL</span>
      </div>

      <div className="cmd-core-row">
        {bottom.map((d) => (
          <DeviceNode key={getDeviceId(d)} device={d} alerts={alerts} position="bottom" />
        ))}
        <Link to="/devices/add" className="cmd-node cmd-node-add">
          <Plus size={16} aria-hidden />
          <span>Add device</span>
        </Link>
      </div>
    </div>
  );
}

function DeviceNode({ device, alerts, position }: {
  device: Device;
  alerts: Alert[];
  position: "top" | "bottom";
}) {
  const deviceId = getDeviceId(device);
  const metricsQuery = useDeviceLatestMetricsQuery(deviceId);
  const metric = metricsQuery.data ?? null;

  const isOnline = (device.status ?? "").toLowerCase() === "online";
  const lastSeen = device.last_seen_at ?? device.last_seen ?? null;
  const stale = lastSeen ? Date.now() - new Date(lastSeen).getTime() > 5 * 60_000 : true;
  const hasAlert = alerts.some((a) => a.device_id === deviceId);
  const state = !isOnline || stale ? "offline" : hasAlert ? "alert" : "live";

  // Pulse the link when fresh telemetry lands (recorded_at moves forward).
  const [pulse, setPulse] = useState(false);
  const lastRecorded = useRef<string | null>(null);
  useEffect(() => {
    const recorded = metric?.recorded_at ?? null;
    if (recorded && lastRecorded.current && recorded !== lastRecorded.current) {
      setPulse(true);
      const t = window.setTimeout(() => setPulse(false), 1400);
      return () => window.clearTimeout(t);
    }
    lastRecorded.current = recorded;
  }, [metric?.recorded_at]);

  const vitals: string[] = [];
  if (metric?.cpu_percent != null) vitals.push(`CPU ${Math.round(metric.cpu_percent)}%`);
  if (metric?.memory_percent != null) vitals.push(`RAM ${Math.round(metric.memory_percent)}%`);
  if (vitals.length === 0 && metric?.battery_percent != null) vitals.push(`Battery ${Math.round(metric.battery_percent)}%`);

  return (
    <Link to={`/devices/${deviceId}`} className={`cmd-node cmd-node-${state} ${pulse ? "cmd-node-pulse" : ""}`}>
      <span className={`cmd-node-link cmd-node-link-${position}`} aria-hidden />
      <p className="cmd-node-name">{device.display_name ?? device.hostname}</p>
      <p className={`cmd-node-state cmd-node-state-${state}`}>
        {state === "live" ? "ONLINE" : state === "alert" ? "ATTENTION" : "OFFLINE"}
      </p>
      {vitals.length > 0 && <p className="cmd-node-meta">{vitals.join(" · ")}</p>}
      <p className="cmd-node-meta">{lastSeen ? relativeTime(lastSeen) : "never seen"}</p>
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/* Backdrop                                                            */
/* ------------------------------------------------------------------ */

/**
 * Sparse drifting signal field on one canvas. Transform/opacity only, capped
 * particle count, paused when the tab is hidden, fully static under
 * prefers-reduced-motion.
 */
function CommandBackdrop({ reducedMotion }: { reducedMotion: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || reducedMotion) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let running = true;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      canvas.width = canvas.offsetWidth * dpr;
      canvas.height = canvas.offsetHeight * dpr;
    };
    resize();
    window.addEventListener("resize", resize);

    const count = window.innerWidth < 768 ? 26 : 60;
    const particles = Array.from({ length: count }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: 0.6 + Math.random() * 1.3,
      vx: (Math.random() - 0.5) * 0.00016,
      vy: -0.00004 - Math.random() * 0.00012,
      a: 0.12 + Math.random() * 0.3,
    }));

    const draw = () => {
      if (!running) return;
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.y < -0.02) { p.y = 1.02; p.x = Math.random(); }
        if (p.x < -0.02) p.x = 1.02;
        if (p.x > 1.02) p.x = -0.02;
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, p.r * dpr, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(225, 60, 70, ${p.a * 0.5})`;
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };

    const onVisibility = () => {
      running = document.visibilityState === "visible";
      if (running) raf = requestAnimationFrame(draw);
      else cancelAnimationFrame(raf);
    };
    document.addEventListener("visibilitychange", onVisibility);
    raf = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reducedMotion]);

  return <canvas ref={canvasRef} className="cmd-backdrop" aria-hidden />;
}

/* ------------------------------------------------------------------ */

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

function shortTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
