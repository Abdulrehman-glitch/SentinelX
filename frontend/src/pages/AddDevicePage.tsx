import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, RefreshCw, Smartphone } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Badge } from "../components/Badge";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { CopyBlock } from "../components/CopyBlock";
import { sentinelxApi } from "../lib/api";
import type { PairingSession, PairingSessionStatus } from "../types/api";

type Platform = "android" | "windows";

// The pairing page drives real backend state: a session is a one-time
// enrolment code, and the status below is polled from the same row the
// agent's enrolment flips — nothing here is scripted timing.
export function AddDevicePage() {
  const [platform, setPlatform] = useState<Platform | null>(null);
  const [session, setSession] = useState<PairingSession | null>(null);
  const [selectedHost, setSelectedHost] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const hostsQuery = useQuery({
    queryKey: ["pairing-hosts"],
    queryFn: sentinelxApi.getPairingHosts,
    staleTime: 60_000,
  });
  const hosts = hostsQuery.data?.hosts ?? [];

  const statusQuery = useQuery({
    queryKey: ["pairing-session", session?.id],
    queryFn: () => sentinelxApi.getPairingSessionStatus(session!.id),
    enabled: session !== null,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      // Stop polling once the pairing reached a terminal state.
      return s === "telemetry_live" || s === "expired" || s === "revoked" ? false : 2500;
    },
  });
  const status: PairingSessionStatus | undefined = statusQuery.data;

  // A paired device should appear in the fleet without a manual refresh.
  useEffect(() => {
    if (status?.status === "enrolled" || status?.status === "telemetry_live") {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    }
  }, [status?.status, queryClient]);

  async function startSession(p: Platform, backendHost?: string | null) {
    setCreating(true);
    setError(null);
    try {
      const created = await sentinelxApi.createPairingSession({
        platform: p,
        backend_url: backendHost ?? undefined,
      });
      setSession(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start a pairing session.");
    } finally {
      setCreating(false);
    }
  }

  function choosePlatform(p: Platform) {
    setPlatform(p);
    setSession(null);
    const host = selectedHost ?? hosts[0]?.address ?? null;
    void startSession(p, host);
  }

  return (
    <div>
      <ConsoleHeader
        eyebrow="Fleet"
        title="Add Device"
        description="Enrol a physical device into this organisation. Pairing codes are one-time and short-lived; the device receives its own credential and starts reporting immediately."
      />

      {/* Platform choice */}
      <div className="mb-6 flex flex-wrap gap-3 sx-animate-in sx-delay-2">
        <PlatformCard
          icon={<Smartphone size={22} />}
          label="Android"
          detail="Scan a QR code with the SentinelX app"
          active={platform === "android"}
          onClick={() => choosePlatform("android")}
        />
        <PlatformCard
          icon={<Laptop size={22} />}
          label="Windows"
          detail="Run a one-line setup on the machine"
          active={platform === "windows"}
          onClick={() => choosePlatform("windows")}
        />
      </div>

      {/* Backend address selection — only interesting with several adapters */}
      {platform !== null && hosts.length > 1 && (
        <div className="sx-panel mb-6 p-5 sx-animate-in sx-delay-3">
          <p className="text-sm font-semibold" style={{ color: "var(--sx-text)" }}>
            Backend reachable at
          </p>
          <p className="mt-1 text-xs" style={{ color: "var(--sx-muted)" }}>
            The device must reach this machine over the network. Pick the address on the same
            network as the device, then restart pairing.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {hosts.map((h) => {
              const active = (selectedHost ?? hosts[0]?.address) === h.address;
              return (
                <button
                  key={h.address}
                  type="button"
                  className={active ? "sx-button-primary rounded-lg px-3 py-2 text-xs font-semibold" : "sx-button-secondary rounded-lg px-3 py-2 text-xs font-semibold"}
                  onClick={() => {
                    setSelectedHost(h.address);
                    if (platform) void startSession(platform, h.address);
                  }}
                >
                  {h.address}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {error && (
        <div className="sx-panel mb-6 border-l-4 p-4 text-sm" style={{ borderLeftColor: "var(--sx-red, #dc2626)", color: "var(--sx-text)" }}>
          {error}
        </div>
      )}

      {platform !== null && session && (
        platform === "android" ? (
          <AndroidPairingPanel session={session} status={status} onRestart={() => startSession("android", selectedHost ?? hosts[0]?.address ?? null)} />
        ) : (
          <WindowsPairingPanel session={session} status={status} onRestart={() => startSession("windows", selectedHost ?? hosts[0]?.address ?? null)} />
        )
      )}

      {platform !== null && !session && creating && (
        <div className="sx-panel p-8 text-center text-sm" style={{ color: "var(--sx-muted)" }}>
          Opening a pairing session…
        </div>
      )}
    </div>
  );
}

function PlatformCard({ icon, label, detail, active, onClick }: {
  icon: React.ReactNode;
  label: string;
  detail: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="sx-panel flex min-w-[240px] items-center gap-4 p-5 text-left transition-shadow"
      style={active ? { borderColor: "var(--sx-accent)", boxShadow: "0 0 0 1px var(--sx-accent)" } : undefined}
    >
      <span style={{ color: active ? "var(--sx-accent)" : "var(--sx-muted)" }}>{icon}</span>
      <span>
        <span className="block text-sm font-bold" style={{ color: "var(--sx-text)" }}>{label}</span>
        <span className="block text-xs" style={{ color: "var(--sx-muted)" }}>{detail}</span>
      </span>
    </button>
  );
}

/** Live pairing progression, derived from the backend session status. */
function PairingStatusLine({ status }: { status?: PairingSessionStatus }) {
  const s = status?.status ?? "waiting";
  const line =
    s === "waiting" ? { tone: "slate" as const, dot: false, text: "Waiting for device…" }
    : s === "enrolled" ? { tone: "blue" as const, dot: true, text: "Device enrolled — securing connection, waiting for first telemetry…" }
    : s === "telemetry_live" ? { tone: "green" as const, dot: true, text: "Connected — telemetry live" }
    : s === "expired" ? { tone: "amber" as const, dot: false, text: "Pairing session expired. Start a new one." }
    : { tone: "red" as const, dot: false, text: "Pairing session revoked." };

  return (
    <div className="flex items-center gap-3">
      {line.dot && <span className="sx-live-dot" aria-hidden />}
      <Badge tone={line.tone}>{line.text}</Badge>
      {status?.device && (s === "enrolled" || s === "telemetry_live") && (
        <Link
          to={`/devices/${status.device.id ?? status.device.device_id ?? ""}`}
          className="text-xs font-semibold underline-offset-2 hover:underline"
          style={{ color: "var(--sx-accent-text, var(--sx-accent))" }}
        >
          {status.device.display_name ?? status.device.hostname}
        </Link>
      )}
    </div>
  );
}

function AndroidPairingPanel({ session, status, onRestart }: {
  session: PairingSession;
  status?: PairingSessionStatus;
  onRestart: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvasRef.current) {
      void QRCode.toCanvas(canvasRef.current, session.qr_payload, {
        width: 260,
        margin: 2,
        color: { dark: "#1c1917", light: "#ffffff" },
      });
    }
  }, [session.qr_payload]);

  const finished = status?.status === "expired" || status?.status === "revoked";

  return (
    <div className="grid gap-6 lg:grid-cols-[auto_1fr] sx-animate-in sx-delay-3">
      <div className="sx-panel flex flex-col items-center gap-4 p-8">
        <h2 className="text-lg font-bold" style={{ color: "var(--sx-text)" }}>Connect Android Agent</h2>
        <p className="max-w-xs text-center text-xs leading-5" style={{ color: "var(--sx-muted)" }}>
          Open the SentinelX app on the phone and scan this QR code.
        </p>
        <canvas ref={canvasRef} className="rounded-xl border" style={{ borderColor: "var(--sx-border)" }} />
        <PairingStatusLine status={status} />
        {finished && (
          <button type="button" className="sx-button-primary mt-2 flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold" onClick={onRestart}>
            <RefreshCw size={14} /> New pairing session
          </button>
        )}
      </div>

      <div className="flex flex-col gap-4">
        <div className="sx-panel p-5">
          <p className="text-sm font-semibold" style={{ color: "var(--sx-text)" }}>No camera? Pair manually</p>
          <p className="mt-1 text-xs leading-5" style={{ color: "var(--sx-muted)" }}>
            In the app choose “Enter pairing code instead” and type the code and server address below.
            The code is single-use and expires at {new Date(session.expires_at).toLocaleTimeString()}.
          </p>
          <div className="mt-3 grid gap-3">
            <CopyBlock title="Pairing code" value={session.code} />
            <CopyBlock title="Server address" value={session.backend_url} />
          </div>
        </div>
        <div className="sx-panel p-5 text-xs leading-5" style={{ color: "var(--sx-muted)" }}>
          The QR carries a short-lived one-time pairing secret — never a device token. The phone
          exchanges it for its own credential, which it stores in Android encrypted storage. Once
          redeemed (or expired) this code is dead.
        </div>
      </div>
    </div>
  );
}

function WindowsPairingPanel({ session, status, onRestart }: {
  session: PairingSession;
  status?: PairingSessionStatus;
  onRestart: () => void;
}) {
  const setupCommand = [
    "cd C:\\SentinelX\\agents\\desktop-python",
    `powershell -ExecutionPolicy Bypass -File setup_windows_agent.ps1 -BackendUrl ${session.backend_url} -PairingCode ${session.code}`,
  ].join("\n");

  const finished = status?.status === "expired" || status?.status === "revoked";

  return (
    <div className="grid gap-6 sx-animate-in sx-delay-3">
      <div className="sx-panel p-6">
        <h2 className="text-lg font-bold" style={{ color: "var(--sx-text)" }}>Connect Windows Agent</h2>
        <p className="mt-1 max-w-2xl text-xs leading-5" style={{ color: "var(--sx-muted)" }}>
          On the computer you want to monitor, open PowerShell in the SentinelX agent folder and run
          the setup command. It installs dependencies, enrols the machine with this one-time code
          (the device token goes straight into Windows Credential Manager), sends the first
          telemetry, and — from an elevated shell — installs the SentinelXAgent service.
        </p>
        <div className="mt-4">
          <CopyBlock title="Setup command (expires at the time below)" value={setupCommand} />
        </div>
        <p className="mt-2 text-xs" style={{ color: "var(--sx-muted)" }}>
          Code expires at {new Date(session.expires_at).toLocaleTimeString()} and can only be used once.
        </p>
        <div className="mt-4">
          <PairingStatusLine status={status} />
        </div>
        {finished && (
          <button type="button" className="sx-button-primary mt-4 flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold" onClick={onRestart}>
            <RefreshCw size={14} /> New pairing session
          </button>
        )}
      </div>
    </div>
  );
}
