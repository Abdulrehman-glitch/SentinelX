import { useState } from "react";
import { Link, useParams } from "react-router";
import { Badge, getStatusTone } from "../components/Badge";
import { ConsoleHeader } from "../components/ConsoleHeader";
import { PermissionGate } from "../components/PermissionGate";
import { RecoveryCommandTimeline } from "../components/RecoveryCommandTimeline";
import { useRecoveryCommandEventsQuery } from "../hooks/useRecoveryCommandEventsQuery";
import {
  useApproveRecoveryCommandMutation,
  useCancelRecoveryCommandMutation,
  useRejectRecoveryCommandMutation,
  useRetryRecoveryCommandMutation,
} from "../hooks/useRecoveryCommandMutations";
import { useRecoveryCommandQuery } from "../hooks/useRecoveryCommandQuery";
import { formatDate, formatLabel, truncateMiddle } from "../utils/format";

const PENDING_APPROVAL_STATUSES = new Set(["proposed", "awaiting_approval"]);
const CANCELLABLE_STATUSES = new Set(["proposed", "awaiting_approval", "approved", "running"]);
const TERMINAL_STATUSES = new Set([
  "rejected", "expired", "failed", "verified", "ineffective", "inconclusive", "rolled_back",
]);

function riskTone(riskLevel: string) {
  if (riskLevel === "high") return "red" as const;
  if (riskLevel === "medium") return "amber" as const;
  return "green" as const;
}

function verificationTone(status: string | null | undefined) {
  if (status === "verified") return "green" as const;
  if (status === "ineffective" || status === "failed") return "red" as const;
  if (status === "inconclusive") return "amber" as const;
  return "slate" as const;
}

export function RecoveryCommandDetailPage() {
  const params = useParams();
  const commandId = params.commandId ?? "";

  const commandQuery = useRecoveryCommandQuery(commandId);
  const eventsQuery = useRecoveryCommandEventsQuery(commandId);

  const approveMutation = useApproveRecoveryCommandMutation(commandId);
  const rejectMutation = useRejectRecoveryCommandMutation(commandId);
  const cancelMutation = useCancelRecoveryCommandMutation(commandId);
  const retryMutation = useRetryRecoveryCommandMutation(commandId);

  const [rejectReason, setRejectReason] = useState("");

  const command = commandQuery.data ?? null;

  const error =
    commandQuery.error ?? eventsQuery.error ?? approveMutation.error ?? rejectMutation.error ??
    cancelMutation.error ?? retryMutation.error;
  const errorMessage =
    error instanceof Error ? error.message : error ? "Unknown error while loading this command." : null;

  async function refresh() {
    await Promise.all([commandQuery.refetch(), eventsQuery.refetch()]);
  }

  // Never conflate "the agent finished running the command" with "the
  // recovery actually worked" — these are always shown as distinct facts.
  const executionSucceeded = command
    ? ["succeeded", "verifying", "verified", "ineffective", "inconclusive", "rolled_back"].includes(command.status)
    : false;
  const verificationPending = command?.status === "verifying";
  const recoveryVerified = command?.status === "verified";

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6">
          <Link to="/recovery-commands" className="text-sm font-semibold sx-c-muted transition hover:text-violet-300">
            ← Back to recovery commands
          </Link>
        </div>

        <ConsoleHeader
          eyebrow="Recovery Command Detail"
          title={command ? command.action_type : "Loading command..."}
          description="Full lifecycle view: signature status, approval, dispatch, execution result, and independent post-action verification."
        >
          <button
            type="button"
            onClick={refresh}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={commandQuery.isFetching || eventsQuery.isFetching}
          >
            {commandQuery.isFetching || eventsQuery.isFetching ? "Refreshing..." : "Refresh"}
          </button>
        </ConsoleHeader>

        {errorMessage && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm sx-c-danger">
            <p className="font-semibold">Command operation failed.</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        )}

        {command && (
          <>
            <section className="grid gap-4 lg:grid-cols-4">
              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Status</p>
                <div className="mt-3">
                  <Badge tone={getStatusTone(command.status)}>{formatLabel(command.status)}</Badge>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Risk / Approval</p>
                <div className="mt-3 flex items-center gap-2">
                  <Badge tone={riskTone(command.risk_level)}>{command.risk_level}</Badge>
                  <span className="text-xs sx-c-text0">{formatLabel(command.approval_mode)}</span>
                </div>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Device</p>
                <p className="mt-3 text-sm font-bold sx-c-text">{truncateMiddle(command.device_id, 24)}</p>
              </article>

              <article className="sx-panel rounded-2xl p-5">
                <p className="text-sm font-semibold sx-c-muted">Signature</p>
                <div className="mt-3">
                  <Badge tone={command.signature ? "green" : "slate"}>
                    {command.signature ? "Signed" : "Not yet signed"}
                  </Badge>
                </div>
                {command.expires_at && (
                  <p className="mt-1 text-xs sx-c-text0">Expires {formatDate(command.expires_at)}</p>
                )}
              </article>
            </section>

            {/* Explicitly distinct execution vs. verification statuses — never
                say "Recovery successful" just because the agent finished. */}
            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Execution &amp; Verification</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border sx-c-border sx-c-surface p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Execution</p>
                  <p className="mt-2 text-sm font-bold sx-c-text">
                    {executionSucceeded
                      ? "Execution succeeded"
                      : command.status === "failed"
                        ? "Execution failed"
                        : "Not yet executed"}
                  </p>
                  {command.result_message && (
                    <p className="mt-2 text-sm leading-6 sx-c-muted">{command.result_message}</p>
                  )}
                </div>

                <div className="rounded-xl border sx-c-border sx-c-surface p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Recovery verification</p>
                  <div className="mt-2">
                    {verificationPending ? (
                      <Badge tone="amber">Verification pending</Badge>
                    ) : recoveryVerified ? (
                      <Badge tone="green">Recovery verified</Badge>
                    ) : (
                      <Badge tone={verificationTone(command.verification_status)}>
                        {command.verification_status ? formatLabel(command.verification_status) : "Not applicable yet"}
                      </Badge>
                    )}
                  </div>
                  {command.verification_message && (
                    <p className="mt-2 text-sm leading-6 sx-c-muted">{command.verification_message}</p>
                  )}
                </div>
              </div>

              {(command.pre_action_snapshot_json || command.post_action_snapshot_json) && (
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-xl border sx-c-border sx-c-surface p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Pre-action evidence</p>
                    <pre className="sx-mono mt-2 max-h-48 overflow-auto text-xs sx-c-muted">
                      {command.pre_action_snapshot_json
                        ? JSON.stringify(command.pre_action_snapshot_json, null, 2)
                        : "None captured."}
                    </pre>
                  </div>
                  <div className="rounded-xl border sx-c-border sx-c-surface p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide sx-c-text0">Post-action evidence</p>
                    <pre className="sx-mono mt-2 max-h-48 overflow-auto text-xs sx-c-muted">
                      {command.post_action_snapshot_json
                        ? JSON.stringify(command.post_action_snapshot_json, null, 2)
                        : "None captured."}
                    </pre>
                  </div>
                </div>
              )}
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Source &amp; Recommendation</h2>
              <p className="mt-2 text-sm leading-6 sx-c-muted">{command.reason ?? "No reason recorded."}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs sx-c-text0">
                <Badge tone={command.decision_source === "ai_proposal" ? "violet" : "slate"}>
                  {formatLabel(command.decision_source)}
                </Badge>
                {command.anomaly_prediction_id && (
                  <Link
                    to={`/anomaly-predictions/${command.anomaly_prediction_id}`}
                    className="sx-mono underline hover:text-violet-300"
                  >
                    View source anomaly prediction
                  </Link>
                )}
                {command.incident_id && (
                  <Link to={`/incidents/${command.incident_id}`} className="sx-mono underline hover:text-violet-300">
                    View linked incident
                  </Link>
                )}
                {command.model_name && (
                  <span>
                    Model: {command.model_name} v{command.model_version}
                    {command.confidence != null ? ` (confidence ${(command.confidence * 100).toFixed(0)}%)` : ""}
                  </span>
                )}
              </div>
            </section>

            <section className="sx-panel mt-8 rounded-2xl p-5">
              <h2 className="text-lg font-bold sx-c-text">Command Controls</h2>

              <PermissionGate
                roles={["admin", "engineer", "owner", "platform_admin"]}
                fallback={
                  <div className="mt-5 rounded-2xl border sx-c-border sx-c-surface p-4 text-sm sx-c-muted">
                    Command controls are read-only for viewers.
                  </div>
                }
              >
                <div className="mt-5 flex flex-wrap items-center gap-3">
                  {PENDING_APPROVAL_STATUSES.has(command.status) && (
                    <button
                      type="button"
                      onClick={() => approveMutation.mutate()}
                      disabled={approveMutation.isPending}
                      className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {approveMutation.isPending ? "Approving..." : "Approve"}
                    </button>
                  )}

                  {CANCELLABLE_STATUSES.has(command.status) && (
                    <button
                      type="button"
                      onClick={() => cancelMutation.mutate()}
                      disabled={cancelMutation.isPending}
                      className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {cancelMutation.isPending ? "Cancelling..." : "Cancel"}
                    </button>
                  )}

                  {TERMINAL_STATUSES.has(command.status) && (
                    <button
                      type="button"
                      onClick={() => retryMutation.mutate()}
                      disabled={retryMutation.isPending}
                      className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {retryMutation.isPending ? "Retrying..." : "Retry (new command)"}
                    </button>
                  )}
                </div>

                {!TERMINAL_STATUSES.has(command.status) && (
                  <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
                    <input
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Reason for rejection..."
                      className="sx-input w-full sm:w-96"
                    />
                    <button
                      type="button"
                      onClick={() => rejectMutation.mutate(rejectReason || "Rejected by operator.")}
                      disabled={rejectMutation.isPending}
                      className="sx-button-secondary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {rejectMutation.isPending ? "Rejecting..." : "Reject"}
                    </button>
                  </div>
                )}
              </PermissionGate>

              <p className="mt-4 text-xs sx-c-text0">
                Created {formatDate(command.created_at)}
                {command.approved_at && ` · Approved ${formatDate(command.approved_at)}`}
                {command.dispatched_at && ` · Dispatched ${formatDate(command.dispatched_at)}`}
                {command.completed_at && ` · Completed ${formatDate(command.completed_at)}`}
              </p>
            </section>

            <RecoveryCommandTimeline events={eventsQuery.data ?? []} />
          </>
        )}
      </section>
    </main>
  );
}
