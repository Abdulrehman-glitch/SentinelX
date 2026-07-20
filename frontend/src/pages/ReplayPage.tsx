import { useState } from "react";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { PermissionGate } from "../components/PermissionGate";
import { ReplayDecisionsTable } from "../components/ReplayDecisionsTable";
import { useReplayMutation } from "../hooks/useReplayMutation";

const DEVICE_CLASSES = ["laptop_windows_v1", "android_mobile_v1"];

function defaultDateTimeLocal(offsetDays: number) {
  const date = new Date(Date.now() + offsetDays * 24 * 60 * 60 * 1000);
  date.setSeconds(0, 0);
  const iso = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString();
  return iso.slice(0, 16);
}

export function ReplayPage() {
  const replayMutation = useReplayMutation();

  const [deviceClass, setDeviceClass] = useState(DEVICE_CLASSES[0]);
  const [periodStart, setPeriodStart] = useState(defaultDateTimeLocal(-7));
  const [periodEnd, setPeriodEnd] = useState(defaultDateTimeLocal(0));
  const [modelVersion, setModelVersion] = useState("");
  const [exportFormat, setExportFormat] = useState<"" | "json" | "markdown">("");

  const errorMessage =
    replayMutation.error instanceof Error
      ? replayMutation.error.message
      : replayMutation.error
        ? "Unknown error while running historical replay."
        : null;

  function runReplay() {
    replayMutation.mutate({
      device_class: deviceClass,
      period_start: new Date(periodStart).toISOString(),
      period_end: new Date(periodEnd).toISOString(),
      model_version: modelVersion || null,
      export_format: exportFormat || null,
    });
  }

  function downloadExport() {
    if (!replayMutation.data?.export) return;
    const ext = exportFormat === "markdown" ? "md" : "json";
    const mime = exportFormat === "markdown" ? "text/markdown" : "application/json";
    const blob = new Blob([replayMutation.data.export], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `replay-${replayMutation.data.device_class}-${replayMutation.data.replay_run_id}.${ext}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Historical Replay"
          title="Backtest the Hybrid Pipeline"
          description="Re-run the hybrid pipeline read-only against stored feature windows — including retired model versions — for backtesting. Never writes an AnomalyPrediction, HybridDecision, Alert, Incident, or RecoveryCommand; only an audit-only run summary is kept."
        />

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Replay run failed.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        <section className="sx-panel rounded-2xl p-5">
          <h2 className="text-lg font-bold sx-c-text">Run parameters</h2>

          <PermissionGate
            roles={["admin", "owner", "engineer", "platform_admin"]}
            fallback={
              <div className="mt-4 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                Running historical replay is restricted to admins and engineers.
              </div>
            }
          >
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide sx-c-text0">
                Device class
                <select value={deviceClass} onChange={(e) => setDeviceClass(e.target.value)} className="sx-input">
                  {DEVICE_CLASSES.map((cls) => (
                    <option key={cls} value={cls}>
                      {cls}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide sx-c-text0">
                Period start
                <input
                  type="datetime-local"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className="sx-input"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide sx-c-text0">
                Period end
                <input
                  type="datetime-local"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className="sx-input"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide sx-c-text0">
                Model version (optional)
                <input
                  value={modelVersion}
                  onChange={(e) => setModelVersion(e.target.value)}
                  placeholder="e.g. 2026-07-18-a"
                  className="sx-input"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide sx-c-text0">
                Export format (optional)
                <select
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value as "" | "json" | "markdown")}
                  className="sx-input"
                >
                  <option value="">No export</option>
                  <option value="json">JSON</option>
                  <option value="markdown">Markdown</option>
                </select>
              </label>
            </div>

            <button
              type="button"
              onClick={runReplay}
              disabled={replayMutation.isPending}
              className="sx-button-primary mt-5 rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {replayMutation.isPending ? "Running replay..." : "Run replay"}
            </button>
          </PermissionGate>
        </section>

        {replayMutation.data && (
          <>
            <section className="mt-8 grid gap-4 lg:grid-cols-4">
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Windows considered</p>
                <p className="mt-3 text-2xl font-bold sx-c-text">{replayMutation.data.windows_considered}</p>
              </article>
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Decisions produced</p>
                <p className="mt-3 text-2xl font-bold sx-c-text">{replayMutation.data.decisions.length}</p>
              </article>
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Scoring policy</p>
                <p className="mt-3 text-sm font-bold sx-c-text">{replayMutation.data.scoring_policy_version}</p>
              </article>
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Model version</p>
                <p className="mt-3 text-sm font-bold sx-c-text">{replayMutation.data.model_version ?? "Any active"}</p>
              </article>
            </section>

            {replayMutation.data.skipped.length > 0 && (
              <div className="mt-6 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                <p className="font-semibold sx-c-text">Skipped windows</p>
                <ul className="mt-2 list-inside list-disc space-y-1">
                  {replayMutation.data.skipped.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {replayMutation.data.export && (
              <div className="mt-6 rounded-2xl border sx-c-border sx-c-surface p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold sx-c-text">Export ({exportFormat})</p>
                  <button type="button" onClick={downloadExport} className="sx-button-secondary rounded-lg px-3 py-1.5 text-xs font-semibold">
                    Download
                  </button>
                </div>
                <pre className="sx-mono mt-3 max-h-64 overflow-auto text-xs sx-c-muted">{replayMutation.data.export}</pre>
              </div>
            )}

            <ReplayDecisionsTable decisions={replayMutation.data.decisions} />
          </>
        )}
      </section>
    </main>
  );
}
