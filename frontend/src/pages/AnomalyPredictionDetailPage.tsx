import { useState } from "react";
import { Link, useParams } from "react-router";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "../components/Badge";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { PermissionGate } from "../components/PermissionGate";
import { useAnomalyPredictionQuery } from "../hooks/useAnomalyPredictionQuery";
import { useReviewAnomalyPredictionMutation } from "../hooks/useObservabilityMutations";
import { useProposeRecoveryFromAnomalyMutation } from "../hooks/useRecoveryCommandMutations";
import type { ReviewStatus } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

// Kept in sync manually with backend/scripts/seed_recovery_policies.py.
const RECOVERY_ACTION_OPTIONS = [
  "collect_diagnostics",
  "rotate_agent_logs",
  "retry_telemetry_sync",
  "repair_agent_queue",
  "restart_sentinelx_agent",
  "restart_allowlisted_service",
  "restart_monitoring_service",
  "reschedule_sync_workers",
  "reset_api_connection",
  "repair_local_database",
  "enter_safe_monitoring_mode",
  "restore_normal_monitoring_mode",
];

const REVIEW_OPTIONS: { value: ReviewStatus; label: string }[] = [
  { value: "true_positive", label: "True positive" },
  { value: "false_positive", label: "False positive" },
  { value: "expected_change", label: "Expected change" },
  { value: "insufficient_context", label: "Insufficient context" },
];

export function AnomalyPredictionDetailPage() {
  const params = useParams();
  const predictionId = params.predictionId ?? "";

  const predictionQuery = useAnomalyPredictionQuery(predictionId);
  const reviewMutation = useReviewAnomalyPredictionMutation(predictionId);
  const proposeRecoveryMutation = useProposeRecoveryFromAnomalyMutation(predictionId);
  const [reviewNote, setReviewNote] = useState("");
  const [recoveryActionType, setRecoveryActionType] = useState(RECOVERY_ACTION_OPTIONS[0]);

  const prediction = predictionQuery.data ?? null;

  const error = predictionQuery.error ?? reviewMutation.error;
  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unknown error while loading this prediction."
        : null;

  const chartData = prediction
    ? Object.entries(prediction.feature_comparison).map(([feature, entry]) => ({
        feature,
        baseline: entry.baseline ?? null,
        actual: entry.actual,
      }))
    : [];

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6">
          <Link to="/anomaly-predictions" className="text-sm font-semibold sx-c-muted transition hover:text-violet-300">
            ← Back to anomaly predictions
          </Link>
        </div>

        <ConsoleHeader
          eyebrow="AI Observability · Prediction Detail"
          title={prediction ? `${prediction.model_name} v${prediction.model_version}` : "Loading prediction..."}
          description="Shadow-mode prediction detail: what changed, how it compares to baseline, and its confidence. Reviewing this never triggers an alert, incident, or recovery action."
        />

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Could not load this prediction.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        {prediction && (
          <>
            <section className="grid gap-4 lg:grid-cols-4">
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Anomaly score</p>
                <p className="mt-3 text-2xl font-bold sx-c-text">{prediction.anomaly_score.toFixed(3)}</p>
                <p className="mt-1 text-xs sx-c-text0">Threshold {prediction.threshold.toFixed(3)} · not a probability</p>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Confidence</p>
                <div className="mt-3">
                  <Badge tone={prediction.confidence === "high" ? "red" : prediction.confidence === "medium" ? "amber" : "slate"}>
                    {prediction.confidence}
                  </Badge>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Device</p>
                <p className="mt-3 text-sm font-bold sx-c-text">{truncateMiddle(prediction.device_id, 24)}</p>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Scored</p>
                <p className="mt-3 text-sm font-bold sx-c-text">{formatDate(prediction.created_at)}</p>
              </article>
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">What changed</h2>
              <p className="mt-2 text-sm leading-6 sx-c-muted">{prediction.explanation}</p>

              {chartData.length > 0 && (
                <div className="mt-6 h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                      <CartesianGrid stroke="rgba(148,163,184,0.16)" strokeDasharray="3 3" />
                      <XAxis dataKey="feature" tick={{ fill: "#94a3b8", fontSize: 11 }} interval={0} angle={-30} textAnchor="end" height={70} />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          background: "rgba(2, 6, 23, 0.94)",
                          border: "1px solid rgba(148, 163, 184, 0.22)",
                          borderRadius: "14px",
                          color: "#e2e8f0",
                        }}
                      />
                      <Legend />
                      <Bar dataKey="baseline" name="Baseline" fill="var(--sx-muted)" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="actual" name="Actual" fill="#0d9488" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Human review</h2>
              <p className="mt-2 text-sm leading-6 sx-c-muted">
                Current status: <Badge tone="slate">{formatLabel(prediction.review_status)}</Badge>
                {prediction.reviewed_at && <span className="ml-2 text-xs sx-c-text0">Reviewed {formatDate(prediction.reviewed_at)}</span>}
              </p>

              <PermissionGate
                roles={["admin", "owner", "engineer", "platform_admin"]}
                fallback={
                  <div className="mt-5 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                    Review labelling is read-only for your role.
                  </div>
                }
              >
                <textarea
                  value={reviewNote}
                  onChange={(e) => setReviewNote(e.target.value)}
                  placeholder="Optional note explaining this label..."
                  className="sx-input mt-4 w-full"
                  rows={2}
                />
                <div className="mt-3 flex flex-wrap gap-3">
                  {REVIEW_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() =>
                        reviewMutation.mutate({ review_status: option.value, review_note: reviewNote || null })
                      }
                      disabled={reviewMutation.isPending}
                      className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </PermissionGate>
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Propose Recovery Command</h2>
              <p className="mt-2 text-sm leading-6 sx-c-muted">
                AI never picks the action or executes anything directly. A human selects an allowlisted
                action here; the deterministic policy engine — not this prediction — decides whether it
                auto-approves or needs manual approval.
              </p>

              <PermissionGate
                roles={["admin", "owner", "engineer", "platform_admin"]}
                fallback={
                  <div className="mt-5 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                    Proposing a recovery command is restricted to admins and engineers.
                  </div>
                }
              >
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <select
                    value={recoveryActionType}
                    onChange={(e) => setRecoveryActionType(e.target.value)}
                    className="sx-input w-full sm:w-72"
                  >
                    {RECOVERY_ACTION_OPTIONS.map((action) => (
                      <option key={action} value={action}>
                        {action}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() =>
                      proposeRecoveryMutation.mutate({ action_type: recoveryActionType, parameters: {} })
                    }
                    disabled={proposeRecoveryMutation.isPending}
                    className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {proposeRecoveryMutation.isPending ? "Proposing..." : "Propose recovery command"}
                  </button>
                </div>

                {proposeRecoveryMutation.isSuccess && proposeRecoveryMutation.data && (
                  <div className="mt-4 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                    Command created with status{" "}
                    <Badge tone="slate">{formatLabel(proposeRecoveryMutation.data.status)}</Badge>.{" "}
                    <Link
                      to={`/recovery-commands/${proposeRecoveryMutation.data.id}`}
                      className="underline hover:text-violet-300"
                    >
                      View in Recovery Command Centre
                    </Link>
                  </div>
                )}
              </PermissionGate>
            </section>
          </>
        )}
      </section>
    </main>
  );
}
