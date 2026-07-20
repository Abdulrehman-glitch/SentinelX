import { useState } from "react";
import { Badge } from "./Badge";
import { useModelEvaluationsQuery } from "../hooks/useModelEvaluationsQuery";
import {
  useEvaluateModelMutation,
  usePromoteModelMutation,
  useRetireModelMutation,
} from "../hooks/useModelLifecycleMutations";
import type { AnomalyModelInfo } from "../types/api";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

const LIFECYCLE_ORDER = ["candidate", "shadow", "advisory", "alert_eligible", "retired"] as const;
const PROMOTE_TARGETS = ["shadow", "advisory", "alert_eligible"] as const;

function lifecycleTone(status: string) {
  if (status === "alert_eligible") return "green" as const;
  if (status === "advisory") return "blue" as const;
  if (status === "shadow") return "amber" as const;
  if (status === "retired") return "red" as const;
  return "slate" as const;
}

function nextRung(status: string): (typeof PROMOTE_TARGETS)[number] {
  const index = LIFECYCLE_ORDER.indexOf(status as (typeof LIFECYCLE_ORDER)[number]);
  const next = LIFECYCLE_ORDER[index + 1];
  return (PROMOTE_TARGETS as readonly string[]).includes(next) ? (next as (typeof PROMOTE_TARGETS)[number]) : "shadow";
}

type ModelLifecycleCardProps = {
  model: AnomalyModelInfo;
};

export function ModelLifecycleCard({ model }: ModelLifecycleCardProps) {
  const evaluationsQuery = useModelEvaluationsQuery(model.id);
  const evaluateMutation = useEvaluateModelMutation(model.id);
  const promoteMutation = usePromoteModelMutation(model.id);
  const retireMutation = useRetireModelMutation(model.id);

  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [targetStatus, setTargetStatus] = useState<(typeof PROMOTE_TARGETS)[number]>(nextRung(model.lifecycle_status));
  const [evaluationReportId, setEvaluationReportId] = useState("");
  const [retireReason, setRetireReason] = useState("");

  const evaluations = evaluationsQuery.data ?? [];
  const isRetired = model.lifecycle_status === "retired";

  const error = evaluateMutation.error ?? promoteMutation.error ?? retireMutation.error;
  const errorMessage =
    error instanceof Error ? error.message : error ? "That model lifecycle action failed." : null;

  function runEvaluation() {
    if (!periodStart || !periodEnd) return;
    evaluateMutation.mutate({
      period_start: new Date(periodStart).toISOString(),
      period_end: new Date(periodEnd).toISOString(),
    });
  }

  return (
    <article className="sx-panel rounded-2xl p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-bold sx-c-text">
            {model.name} <span className="sx-mono text-sm sx-c-muted">v{model.version}</span>
          </h3>
          <p className="mt-1 text-xs sx-c-text0">
            {model.device_class} · {model.algorithm} · schema {model.feature_schema_version}
          </p>
        </div>
        <Badge tone={lifecycleTone(model.lifecycle_status)}>{formatLabel(model.lifecycle_status)}</Badge>
      </div>

      <div className="mt-4 grid gap-3 text-xs sx-c-text0 sm:grid-cols-2">
        <p>Trained {formatDate(model.trained_at)}</p>
        <p>Active: {model.is_active ? "Yes" : "No"}</p>
        <p>Checksum: {model.artifact_checksum ? truncateMiddle(model.artifact_checksum, 20) : "Not recorded"}</p>
        <p>{model.promoted_at ? `Promoted ${formatDate(model.promoted_at)}` : "Never promoted"}</p>
      </div>

      {errorMessage && (
        <div className="mt-4 rounded-xl border border-rose-400/25 bg-rose-400/10 p-3 text-xs sx-c-danger">
          {errorMessage}
        </div>
      )}

      {!isRetired && (
        <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--sx-border)" }}>
          <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Evaluate</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
              type="datetime-local"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="sx-input"
              aria-label="Evaluation period start"
            />
            <span className="text-xs sx-c-text0">to</span>
            <input
              type="datetime-local"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="sx-input"
              aria-label="Evaluation period end"
            />
            <button
              type="button"
              onClick={runEvaluation}
              disabled={evaluateMutation.isPending || !periodStart || !periodEnd}
              className="sx-button-secondary rounded-xl px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {evaluateMutation.isPending ? "Evaluating..." : "Run evaluation"}
            </button>
          </div>

          {evaluations.length > 0 && (
            <div className="mt-3 space-y-2">
              {evaluations.map((report) => (
                <label
                  key={report.id}
                  className="flex cursor-pointer flex-wrap items-center gap-3 rounded-lg border px-3 py-2 text-xs"
                  style={{ borderColor: "var(--sx-border)" }}
                >
                  <input
                    type="radio"
                    name={`evaluation-${model.id}`}
                    checked={evaluationReportId === report.id}
                    onChange={() => setEvaluationReportId(report.id)}
                  />
                  <span className="sx-c-text">
                    {formatDate(report.period_start)} → {formatDate(report.period_end)}
                  </span>
                  <span className="sx-c-muted">{report.reviewed_count} reviewed</span>
                  <span className="sx-c-muted">
                    FP rate {report.false_positive_rate != null ? `${(report.false_positive_rate * 100).toFixed(0)}%` : "n/a"}
                  </span>
                  <span className="sx-c-muted">
                    Precision {report.precision != null ? `${(report.precision * 100).toFixed(0)}%` : "n/a"}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {!isRetired && (
        <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--sx-border)" }}>
          <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Promote</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <select
              value={targetStatus}
              onChange={(e) => setTargetStatus(e.target.value as (typeof PROMOTE_TARGETS)[number])}
              className="sx-input"
            >
              {PROMOTE_TARGETS.map((target) => (
                <option key={target} value={target}>
                  {formatLabel(target)}
                </option>
              ))}
            </select>
            <select
              value={evaluationReportId}
              onChange={(e) => setEvaluationReportId(e.target.value)}
              className="sx-input"
            >
              <option value="">No evaluation report</option>
              {evaluations.map((report) => (
                <option key={report.id} value={report.id}>
                  {formatDate(report.created_at)}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() =>
                promoteMutation.mutate({
                  target_status: targetStatus,
                  evaluation_report_id: evaluationReportId || null,
                })
              }
              disabled={promoteMutation.isPending}
              className="sx-button-primary rounded-xl px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {promoteMutation.isPending ? "Promoting..." : "Promote"}
            </button>
          </div>
          <p className="mt-2 text-xs sx-c-text0">
            Past shadow, promotion needs a linked evaluation report with ≥20 reviewed predictions and ≤30% false-positive rate.
          </p>
        </div>
      )}

      {!isRetired && (
        <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--sx-border)" }}>
          <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Retire</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
              value={retireReason}
              onChange={(e) => setRetireReason(e.target.value)}
              placeholder="Reason for retiring this model..."
              className="sx-input w-full sm:w-80"
            />
            <button
              type="button"
              onClick={() => retireMutation.mutate({ reason: retireReason || "Retired by operator." })}
              disabled={retireMutation.isPending}
              className="sx-button-secondary rounded-xl px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {retireMutation.isPending ? "Retiring..." : "Retire model"}
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
