import { useState } from "react";
import { Link, useParams } from "react-router";
import { Badge, getSeverityTone } from "../components/Badge";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { PermissionGate } from "../components/PermissionGate";
import { useHybridDecisionQuery } from "../hooks/useHybridDecisionQuery";
import {
  useProposeRecoveryFromHybridDecisionMutation,
  useReviewHybridDecisionMutation,
} from "../hooks/useHybridDetectionMutations";
import type { ReviewHybridDecisionPayload } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

const REVIEW_OPTIONS: { value: ReviewHybridDecisionPayload["review_status"]; label: string }[] = [
  { value: "true_positive", label: "True positive" },
  { value: "false_positive", label: "False positive" },
  { value: "expected_change", label: "Expected change" },
  { value: "insufficient_context", label: "Insufficient context" },
  { value: "duplicate", label: "Duplicate" },
];

function riskTone(risk: string) {
  if (risk === "high") return "red" as const;
  if (risk === "medium") return "amber" as const;
  return "green" as const;
}

function agreementTone(agreement: string) {
  if (agreement === "all_agree") return "red" as const;
  if (agreement === "two_agree") return "amber" as const;
  if (agreement === "detector_conflict") return "blue" as const;
  if (agreement === "all_normal") return "green" as const;
  if (agreement === "insufficient_data") return "slate" as const;
  return "violet" as const;
}

export function HybridDecisionDetailPage() {
  const params = useParams();
  const decisionId = params.decisionId ?? "";

  const decisionQuery = useHybridDecisionQuery(decisionId);
  const reviewMutation = useReviewHybridDecisionMutation(decisionId);
  const proposeRecoveryMutation = useProposeRecoveryFromHybridDecisionMutation(decisionId);
  const [reviewNote, setReviewNote] = useState("");

  const decision = decisionQuery.data ?? null;

  const error = decisionQuery.error ?? reviewMutation.error ?? proposeRecoveryMutation.error;
  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unknown error while loading this decision."
        : null;

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6">
          <Link to="/hybrid-decisions" className="text-sm font-semibold sx-c-muted transition hover:text-violet-300">
            ← Back to hybrid decisions
          </Link>
        </div>

        <ConsoleHeader
          eyebrow="Hybrid Detection · Decision Detail"
          title={decision ? `Decision for ${truncateMiddle(decision.device_id, 20)}` : "Loading decision..."}
          description="How the deterministic alert rules, statistical baseline, and IsolationForest combined into one judgement — and why."
        />

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Could not complete that action.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        {decision && (
          <>
            <section className="grid gap-4 lg:grid-cols-4">
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Detector agreement</p>
                <div className="mt-3">
                  <Badge tone={agreementTone(decision.detector_agreement)}>
                    {formatLabel(decision.detector_agreement)}
                  </Badge>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Combined severity</p>
                <div className="mt-3">
                  <Badge tone={getSeverityTone(decision.combined_severity)}>{decision.combined_severity}</Badge>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Operational risk</p>
                <div className="mt-3">
                  <Badge tone={riskTone(decision.operational_risk)}>{decision.operational_risk}</Badge>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Confidence</p>
                <p className="mt-3 text-sm font-bold sx-c-text">{formatLabel(decision.confidence)}</p>
              </article>
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Why this decision</h2>
              <p className="mt-2 text-sm leading-6 sx-c-muted">{decision.explanation}</p>

              {decision.affected_features.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {decision.affected_features.map((feature) => (
                    <Badge key={feature} tone="slate">
                      {feature}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="mt-6 grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border sx-c-border sx-c-surface p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Rule result</p>
                  <p className="mt-2 text-sm font-bold sx-c-text">
                    {decision.rule_result.fired ? `Fired (${decision.rule_result.severity ?? "unknown"})` : "Not fired"}
                  </p>
                  {decision.rule_result.alert_types && decision.rule_result.alert_types.length > 0 && (
                    <p className="mt-1 text-xs sx-c-text0">{decision.rule_result.alert_types.join(", ")}</p>
                  )}
                </div>
                <div className="rounded-xl border sx-c-border sx-c-surface p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Statistical baseline</p>
                  <p className="mt-2 text-sm font-bold sx-c-text">
                    {decision.baseline_score != null ? decision.baseline_score.toFixed(3) : "Not scored"}
                  </p>
                </div>
                <div className="rounded-xl border sx-c-border sx-c-surface p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">IsolationForest</p>
                  <p className="mt-2 text-sm font-bold sx-c-text">
                    {decision.model_prediction != null ? decision.model_prediction.toFixed(3) : "Not scored"}
                  </p>
                  {decision.model_name && (
                    <p className="mt-1 text-xs sx-c-text0">
                      {decision.model_name} v{decision.model_version}
                    </p>
                  )}
                </div>
              </div>

              <p className="mt-4 text-xs sx-c-text0">
                Scoring policy {decision.scoring_policy_version} · Scored {formatDate(decision.created_at)}
              </p>
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Linked records</h2>
              <div className="mt-3 flex flex-wrap gap-3 text-sm">
                {decision.alert_id && <span className="sx-c-muted">Alert: {truncateMiddle(decision.alert_id, 20)}</span>}
                {decision.incident_id && (
                  <Link to={`/incidents/${decision.incident_id}`} className="sx-mono underline hover:text-violet-300">
                    View linked incident
                  </Link>
                )}
                {decision.recovery_command_id && (
                  <Link
                    to={`/recovery-commands/${decision.recovery_command_id}`}
                    className="sx-mono underline hover:text-violet-300"
                  >
                    View recovery command
                  </Link>
                )}
                {!decision.alert_id && !decision.incident_id && !decision.recovery_command_id && (
                  <span className="sx-c-text0">Nothing linked yet.</span>
                )}
              </div>
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Human review</h2>
              <p className="mt-2 text-sm leading-6 sx-c-muted">
                Current status: <Badge tone="slate">{formatLabel(decision.review_status)}</Badge>
                {decision.reviewed_at && <span className="ml-2 text-xs sx-c-text0">Reviewed {formatDate(decision.reviewed_at)}</span>}
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
                Unlike an anomaly prediction, this proposal doesn't ask you to pick an action — it's deterministically
                derived from the decision itself (collect diagnostics, or retry the telemetry sync when data is
                insufficient) and still goes through the full policy/signing pipeline unchanged. It can also come back
                empty if nothing is actionable or the policy engine declines it.
              </p>

              <PermissionGate
                roles={["admin", "owner", "engineer", "platform_admin"]}
                fallback={
                  <div className="mt-5 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                    Proposing a recovery command is restricted to admins and engineers.
                  </div>
                }
              >
                <button
                  type="button"
                  onClick={() => proposeRecoveryMutation.mutate()}
                  disabled={proposeRecoveryMutation.isPending}
                  className="sx-button-primary mt-4 rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {proposeRecoveryMutation.isPending ? "Proposing..." : "Propose recovery command"}
                </button>

                {proposeRecoveryMutation.isSuccess && (
                  <div className="mt-4 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                    {proposeRecoveryMutation.data ? (
                      <>
                        Command created with status{" "}
                        <Badge tone="slate">{formatLabel(proposeRecoveryMutation.data.status)}</Badge>.{" "}
                        <Link
                          to={`/recovery-commands/${proposeRecoveryMutation.data.id}`}
                          className="underline hover:text-violet-300"
                        >
                          View in Recovery Command Centre
                        </Link>
                      </>
                    ) : (
                      "Nothing was proposed — either there was nothing actionable, or the policy engine declined it (cooldown, daily limit, or circuit breaker)."
                    )}
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
