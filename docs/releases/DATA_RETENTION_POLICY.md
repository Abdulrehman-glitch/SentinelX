# Data Retention Policy (Sprint 7 Phase 6)

Scope: this is a **policy document plus a read-only compliance report**
(`backend/app/db/data_retention_report.py`). No automatic or scheduled
deletion of production data is implemented this sprint — see "Why no
deletion yet" below. The retention periods here are the recommended
targets a future sprint's deletion job should enforce.

## Retention periods by table

| Table | Timestamp column | Retention | Why |
|---|---|---|---|
| `system_metrics` | `recorded_at` | 90 days | Raw per-device telemetry samples (CPU/memory/disk/battery/network) at a few-minute cadence — highest volume table in the system. Near-term troubleshooting value; older raw samples are already summarized into `telemetry_feature_windows`. |
| `agent_heartbeats` | `recorded_at` | 90 days | Same volume/value profile as `system_metrics`. |
| `embedded_telemetry` | `recorded_at` | 90 days | Arduino/embedded sensor readings — same reasoning as agent telemetry. |
| `telemetry_feature_windows` | `window_end` | 180 days | Rolling aggregated feature windows that feed the hybrid detection engine and historical replay. Kept twice as long as raw telemetry because `POST /replay/run` backtests against this table, and model retraining wants a couple of quarters of history. |
| `anomaly_predictions` | `created_at` | 365 days | Individual model predictions. `ModelEvaluationReport` generation (`POST /observability/models/{id}/evaluate`) needs a real review history — the promotion gate requires ≥20 reviewed predictions — so these can't be pruned aggressively. |
| `hybrid_decisions` | `created_at` | 365 days | Same reasoning as `anomaly_predictions`: these are the record a `ModelEvaluationReport` and human review workflow depend on. |
| `recovery_commands` / `recovery_command_events` | `created_at` | 365 days | Safety-critical evidence of automated actions taken on customer systems (what was proposed, signed, approved, executed, verified). This is the audit trail for self-healing — err on the side of keeping it. |
| `replay_runs` | `created_at` | 730 days | Audit-only record of who ran a backtest, over what period, with what result — small row count (one row per replay invocation, not per window), so there's little cost to keeping it as long as `audit_logs`. |
| `audit_logs` | `created_at` | 730 days | General audit trail (auth events, device enrolment, incident lifecycle, config changes). Two years matches typical compliance/forensics expectations for this kind of record. |
| `security_logs` | `created_at` | 730 days | Auth/device-token/rate-limit forensics — same reasoning as `audit_logs`; this is exactly the record you want available if investigating a security incident well after the fact. |

Tables **not** listed (`organizations`, `users`, `devices`, `incidents`,
`alerts`, `alert_rules`, `anomaly_models`, `model_evaluation_reports`,
`enrollment_codes`, `device_credentials`, `recovery_policies`,
`agent_capabilities`) are reference/low-cardinality/business-record tables
(one row per tenant/user/device/incident/model, not per telemetry sample)
and are out of scope for time-based retention — they age out naturally by
becoming inactive, not by volume.

## Why no deletion yet

Sprint 7 is a hardening/release sprint, and prod currently has essentially
**zero data past any of these cutoffs** (see Phase 0's baseline finding:
production's schema itself was pre-Sprint-1 until this sprint's migrations
landed, so most of these tables have only ever existed on the live database
for a short window). Writing and running a real deletion job against
production with no retention history to validate against is a bigger risk
than the problem it solves right now. The dry-run report
(`data_retention_report.py`) exists so that:

1. This sprint proves the policy's numbers are sane by running the report
   against real data (local `sentinelx_dev`, and — once the policy's been
   lived with for a while — production) before anyone writes a deletion
   job against them.
2. A future sprint can implement the actual deletion (a scheduled job or
   an admin-triggered endpoint) against a policy that's already been
   reviewed and reported on, rather than deciding retention periods and
   writing destructive SQL in the same sprint.

## Running the report

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.db.data_retention_report
```

Prints, per table: total row count, the retention-policy cutoff date, and
how many rows are older than that cutoff (i.e. would be deleted by a future
enforcement job). Read-only — issues no `DELETE`/`UPDATE` statements.
