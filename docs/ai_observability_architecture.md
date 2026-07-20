# AI Observability Foundation (Sprint 2)

Shadow-mode, explainable anomaly detection that runs *alongside* — never in place of — the deterministic alert pipeline (`metrics.py::_raise_alerts_for_sample`, `alert_rule_service.py`, `anomaly_service.py`). This sprint earns the right to *watch and explain*, not to act. Nothing here creates `Alert`, `Incident`, or `RecoveryAction` rows, and nothing here is triggered automatically by telemetry ingestion.

## Data flow

```
system_metrics (existing, untouched)
      │  read-only queries, no new columns
      ▼
[quality validator]  →  quality_score + quality_flags per candidate window
      ▼
[feature window builder]  →  tumbling 30-min windows, per device_class schema
      ▼
telemetry_feature_windows
      ▼
[statistical baseline detector]        [IsolationForest — laptop_windows_v1 only]
 (deterministic, always runs)           (loads trained artifact from anomaly_models)
      │                                        │
      └──────────────┬─────────────────────────┘
                      ▼
          anomaly_predictions (shadow_mode=True always)
                      ▼
     GET/PATCH /observability/* (org-scoped, RBAC)  →  frontend review page
```

Entry point: `POST /observability/pipeline/run` (`admin`/`owner`/`engineer`/`platform_admin` only). There is no automatic trigger on metric ingestion — see "Why the pipeline is manually triggered" below.

## Device-class mapping (v1 scope)

`app/services/device_class_service.py::classify(device)`:

- `device_type == "desktop"` and `os_name` contains "windows" (case-insensitive) → `laptop_windows_v1`
- `device_type == "mobile"` and `agent_type == "android_mobile_agent"` → `android_mobile_v1`
- everything else (Linux servers, gateways, embedded/Arduino) → `None`, not scored

This is a deliberate v1 scoping decision, not an oversight: the seeded CNC/edge-gateway devices are Linux servers with fundamentally different load profiles than a laptop, and scoring them against a laptop-shaped baseline would be misleading. Widening device-class coverage is future-sprint work.

## Data-quality validation (`app/services/telemetry_quality_service.py`)

`assess_quality(samples)` returns a `QualityReport(score, flags)` in `[0, 1]`, checking:

- **Range validity** — cpu/memory/disk/battery/temperature bounds (penalised).
- **Duplicate `event_id`** ratio within the window (penalised) — separate from Sprint 1's DB-level uniqueness constraint, which only prevents duplicates *within one device*; this catches duplicates that legitimately differ by device but still degrade a single window's signal.
- **Stale gaps** — consecutive samples further apart than 3× the expected interval (penalised).
- **Clock skew** — `now() - latest_sample.recorded_at` at window-build time (penalised past a threshold). Forward clock skew is already impossible at ingestion (Sprint 1 clamps `recorded_at` to `now()` in `metrics.py`), so this measures *staleness*, not spoofing.
- **Null CPU ratio** — informational only, **not penalised**. A null `cpu_percent` is a valid, expected value for mobile agents (Sprint 1: "unknown CPU must be storable as NULL, never fabricated 0%"), so penalising it would punish correct agent behaviour.

`MIN_QUALITY_SCORE_FOR_SCORING = 0.6` gates whether a window is eligible for detector scoring (not whether a window row is created — every closed window gets a row, even a low-quality one, so the pipeline's progress cursor always advances).

## Feature windows (`app/services/feature_window_service.py`)

Tumbling (non-overlapping) 30-minute windows, minimum 6 samples for a "full" window (`MIN_SAMPLES_PER_WINDOW`). Idempotent: a cursor derived from the latest existing window (or the device's earliest metric on first run) means re-running `build_pending_windows` never reprocesses a window, enforced additionally by `UNIQUE(device_id, feature_schema_version, window_start)`.

Feature vector per window (`app/ml/feature_schemas.py`), core set shared by both device classes:

```
cpu_median, cpu_mad, cpu_ewma, cpu_slope,
memory_median, memory_mad, memory_ewma, memory_slope,
disk_median, disk_mad, disk_ewma, disk_slope
```

`android_mobile_v1` adds: `battery_drain_rate, battery_temperature_median, thermal_hot_ratio, network_metered_ratio` (`thermal_hot_ratio` uses Android's confirmed `PowerManager` enum: `moderate|severe|critical|emergency|shutdown` count against `none|light`).

Feature order is fixed and versioned (`FEATURE_SCHEMA_VERSION = "v1"`) — it's the vector order the ML model is trained and scored on. A schema change means a new version, not an in-place reorder.

## Deterministic statistical baseline (`app/services/statistical_baseline_service.py`)

Always runs, for any classified device with ≥5 prior windows (`MIN_PRIOR_WINDOWS`):

1. Baseline = median + MAD of each feature across the last 20 prior windows (`BASELINE_LOOKBACK`), leave-current-out.
2. Robust modified z-score per feature: `0.6745 × (actual − baseline_median) / max(baseline_mad, MAD_FLOOR)`. The MAD floor (0.5) prevents a division blow-up on a perfectly flat window.
3. `anomaly_score` = the max `|z|` across tracked features.
4. **Sustained-duration gate**: a feature only counts toward `is_anomalous` if the anomaly persists across ≥2 consecutive windows (`SUSTAINED_MIN_WINDOWS`), walked backward through prior `AnomalyPrediction` rows via temporal contiguity (`window_end == next.window_start`). This is the single-window-noise guard — a one-off CPU spike does not flip `is_anomalous`.
5. `confidence` is a qualitative bucket (`low`/`medium`/`high`) derived from sustained-duration + the window's `quality_score` — never derived from `anomaly_score` itself.
6. `feature_comparison` (JSONB) stores `{baseline, actual, z_score, is_affected}` per tracked feature — this single column serves both "affected features" and "baseline comparison" in the API/frontend.
7. Self-registers its own `anomaly_models` row (`algorithm="statistical_baseline"`, `dataset_hash="deterministic"`) on first use — it needs no training step, but still gets full version/hyperparameter provenance like the ML model.

## IsolationForest (`laptop_windows_v1` only)

**Training is an offline, manual script — never triggered from a web request.** This is a deliberate operational decision: an unsupervised model quietly retraining itself inside a live request is an MLOps anti-pattern (silent drift, no review gate, hard to reproduce). The bridge between training and inference is exactly one thing: a row in `anomaly_models` plus its `artifact_path`.

1. `scripts/export_feature_dataset.py` — queries `telemetry_feature_windows` filtered by device_class/schema/quality threshold, flattens into a pandas DataFrame in the fixed feature order, sorted deterministically by `(device_id, window_start)`, writes Parquet. Same query + same DB state ⇒ byte-identical output.
2. `scripts/train_laptop_isolation_forest.py` — fits `sklearn.ensemble.IsolationForest(contamination=0.05, n_estimators=200, random_state=42)`, computes a score-percentile threshold *from the training data itself* (so inference never needs to recompute it), serializes via `joblib`, records `dataset_hash` (SHA-256 of the Parquet file), `code_commit` (`git rev-parse HEAD`), and `hyperparameters` in `anomaly_models`. Deactivates any previously active model for the same device class first — only one active model per class at a time.
3. `app/services/isolation_forest_service.py::score()` loads the active model (in-process cache), scores the window's feature vector, and **negates** sklearn's `decision_function` output so a higher `anomaly_score` always means "more anomalous" — matching the statistical baseline's convention. If no active model is registered, it returns `None` (skip, not error) — the pipeline still runs the statistical baseline for that window.

### `anomaly_score` is never a probability

Both detectors store a raw score (a robust z-score, or a negated IsolationForest decision-function value). Neither is run through a sigmoid or otherwise rescaled to look like `P(anomaly)` — that would fabricate a precision the underlying statistics don't have. `confidence` is a separate, explicitly qualitative field (`low`/`medium`/`high`) for exactly this reason: it's how the system communicates trust without pretending to quantify it.

IsolationForest is also an ensemble black box: unlike the statistical baseline, it has no clean per-feature attribution. `feature_comparison` entries for ML predictions carry `actual` but `baseline`/`z_score`/`is_affected` are left `None` rather than fabricated — an honest limitation, not a bug.

## Why the pipeline is manually triggered

`POST /observability/pipeline/run` is admin/engineer-gated and must be called explicitly — it is **not** wired into `metrics.py`'s ingestion path. This was a deliberate scope decision (confirmed with the project owner before implementation): Sprint 1 had just stabilized and fully tested the metric-ingestion hot path, and coupling a new, still-evolving ML pipeline into that path would risk regressing tested, production-critical code for a feature whose entire purpose is "shadow mode, reviewed periodically" — not real-time. A scheduled/cron trigger calling the same endpoint is a natural follow-up, out of scope for this sprint.

## RBAC & tenant isolation

- Viewing predictions (`GET /observability/anomaly-predictions*`): all authenticated roles, always org-scoped (`assert_same_org`, 404-not-403 on cross-tenant access to avoid ID enumeration — same convention as the rest of the API).
- Triggering the pipeline and submitting review labels: `admin`/`owner`/`engineer`/`platform_admin` only.
- Viewing the model registry (`GET /observability/models`): `admin`/`owner`/`platform_admin` only (internal ML-ops detail).
- `observability_shadow_mode_enabled` (Settings, default `True`) is an instant kill switch for `pipeline/run` — flip to `False` to disable without a code rollback.

## Human review labels

`review_status` on `anomaly_predictions`: `unreviewed` (default) → one of `true_positive`, `false_positive`, `expected_change`, `insufficient_context`. Set via `PATCH /observability/anomaly-predictions/{id}/review`, which stamps `reviewed_by`/`reviewed_at`. These labels are pure human feedback — they do not currently feed back into training (a natural future-sprint use: building a labeled dataset for supervised refinement).

## Rollback strategy

Everything in this sprint is additive:

- **Instant kill switch**: `observability_shadow_mode_enabled=False`.
- **Code rollback**: `git revert` — `metrics.py` and the alert pipeline are untouched, so nothing else depends on these modules.
- **Schema rollback**: `DROP TABLE anomaly_predictions, telemetry_feature_windows, anomaly_models;` is safe — zero incoming foreign keys from any pre-existing table.
- **Dependency rollback**: `scikit-learn`/`pandas`/`pyarrow`/`numpy`/`joblib` are additive to `backend/requirements.txt`; nothing else imports them.
- **Frontend rollback**: new route/page/nav-entry/API-methods only — no shared component was modified.

## Tests

`tests/backend/test_ai_observability.py` (20 tests) covers: feature-calculation correctness (median/MAD/EWMA/slope/z-score against known values), quality-validator behavior for every check dimension, device-class mapping, feature-window idempotency, deterministic re-scoring for both detectors, the model-loading / model-version-mismatch case (no active model ⇒ `None`, never an exception), tenant isolation (cross-org 404), and RBAC (viewer can read, cannot review or trigger the pipeline). All 13 pre-existing Sprint 1 tests continue to pass unchanged.

---

# Hybrid Detection, Model Lifecycle & Historical Replay (Sprint 4-6)

Builds on the Sprint 2 shadow-mode foundation above without replacing it: reuses `telemetry_feature_windows` and both detectors (statistical baseline + IsolationForest), and continues to leave `alerts`/`incidents`/`recovery_commands` under the authoritative deterministic pipeline. Three purely additive stages, each independently killable via a Settings flag.

## Stage 1 — Hybrid Detection Engine (`app/services/hybrid_detection_service.py`)

Combines four signal sources into one deterministic, versioned `HybridDecision` per `(feature_window, scoring_policy_version)`:

1. **Rule result** — read-only lookup of whatever `Alert` rows the existing deterministic pipeline (`metrics.py`) already raised for the window's time span. Never creates or modifies an `Alert`.
2. **Statistical baseline** score/anomalous flag (Sprint 2, always available for a classified device).
3. **IsolationForest** score/anomalous flag (`laptop_windows_v1` only, `None` if no valid active model — see model lifecycle below).
4. **Context**: device `criticality` (low/medium/high, operator-set on `Device`), whether an `Incident` is currently open for the device, and recent (24h) `RecoveryCommand` activity (count + failures).

Pipeline: `POST /hybrid/decisions/run` (device-scoped or org-wide) calls `feature_window_service.build_pending_windows` then scores every window not yet decided at the current `HYBRID_SCORING_POLICY_VERSION` (`"v1"`). Idempotent — re-running is a no-op for already-scored windows (`UNIQUE(feature_window_id, scoring_policy_version)`).

Derivation logic (pure functions, unit-tested directly):

- **`detector_agreement`**: `insufficient_data` (quality below threshold, or no detector produced a signal) → `detector_conflict` (baseline and model disagree, no rule fired) → otherwise a vote count across `{rule, baseline, model}`: `all_normal`, `<x>_only`, `two_agree`, `all_agree`.
- **`combined_severity`**: rules are authoritative — a fired rule's severity is the floor via `max()`; AI-only agreement (`all_agree`, or `two_agree` at medium+ confidence) can raise severity but can never suppress or downgrade a rule-fired severity.
- **`operational_risk`** (low/medium/high): weighted score from combined severity + device criticality + sustained persistence (≥3 windows) + an open incident + recent recovery failures.
- **Persistence**: walks backward through prior `HybridDecision` rows via `TelemetryFeatureWindow.window_end == next.window_start` temporal contiguity, capped at 10 windows.
- **`explanation`**: a generated, human-readable sentence citing exactly which detectors fired and why — never a static template.

`alert_id`/`incident_id`/`recovery_command_id` on `HybridDecision` are read-only references to whatever the authoritative pipelines already produced — this module never writes to any of those three tables itself.

Kill switch: `hybrid_detection_enabled` (Settings, default `True`).

## Stage 2 — Model Lifecycle & Evaluation

**Lifecycle** (`app/models/anomaly_model.py` + `app/services/model_promotion_service.py`): every `AnomalyModel` now carries `lifecycle_status` (`candidate → shadow → advisory → alert_eligible`, plus `retired` from any state), `artifact_checksum`, `promoted_by`, `promoted_at`. Promotion moves exactly one stage forward per call (`POST /observability/models/{id}/promote`) and is gated:

- **Structural gates** (every promotion): feature-schema match against the current `FEATURE_SCHEMA_VERSION`, and artifact checksum verification (`app/ml/model_loader.py::compute_artifact_checksum`) — a changed/tampered file on disk blocks promotion.
- **Evaluation gates** (every promotion past `shadow`, since `candidate → shadow` has no prediction history yet): the linked `ModelEvaluationReport` must show ≥20 reviewed predictions and a false-positive rate ≤30%.

Retirement (`POST /observability/models/{id}/retire`) is a one-way terminal transition from any non-retired state, requires a reason, and is unconditional (no gates — an operator can always pull a model).

`app/ml/model_loader.py::validate()` is now the single inference guard, called from both `isolation_forest_service.score()` and replay: rejects `retired` models, feature-schema drift, and checksum mismatch — always fails closed and quiet (returns a reason, never raises), matching the rest of the pipeline's "skip, don't crash" design.

**Evaluation** (`app/services/model_evaluation_service.py`, `POST /observability/models/{id}/evaluate`): computes a `ModelEvaluationReport` over a period using only human-reviewed `AnomalyPrediction` rows as labels — `precision`/`false_positive_rate` from true_positive/false_positive counts, `detector_agreement_breakdown` (via linked `HybridDecision` rows), `missing_feature_rate`, and a best-effort `anomaly_lead_time_seconds_avg` (time from a true-positive prediction to the next `Incident` on that device). **Never computes recall** — there is no reliable ground-truth "known positive" set in this system, only what a human chose to review; fabricating one would be dishonest. `inference_failures` is left `null` — a metric this system doesn't yet capture, not a fabricated zero.

All promotions/retirements are audit-logged (`audit_log_service`, action `model_promoted`/`model_retired`).

## Stage 3 — Historical Replay (`app/services/replay_service.py`, `POST /replay/run`)

Read-only backtesting: reuses `hybrid_detection_service`'s pure combination functions (rule lookup, agreement, severity, risk, persistence — all read-only) plus read-only equivalents of both detectors' scoring, against a chosen `device_class` + date range + optional specific `model_version` (including a *retired* one — replay bypasses the live-inference `lifecycle_status != retired` filter by design, since comparing a retired model's historical judgment is the entire point). **Never creates or modifies** `AnomalyPrediction`, `HybridDecision`, `Alert`, `Incident`, or `RecoveryCommand` — the only side effect is one audit-only `ReplayRun` summary row (who ran it, what parameters, how many windows/decisions). Reproducible for a fixed DB state. Supports `json`/`markdown` export of the full decision list.

Kill switch: `historical_replay_enabled` (Settings, default `True`), independent of the hybrid-detection flag since replay's read-only property makes it a lower-risk toggle.

## Verified low-risk self-healing (Sprint 4-6, Stage 4-5)

`app/services/ai_recommendation_service.py` deterministically maps a `HybridDecision` to *at most one* action from a narrow, hardcoded allowlist — `{collect_diagnostics, retry_telemetry_sync}` — far smaller than the full 12-action `recovery_policies` allowlist. Every recommendation goes through the *exact same* `recovery_command_service.create_command()` path as manual and anomaly-triggered proposals: same policy engine, same cooldown/circuit-breaker checks, same signed command lifecycle. This module never executes, approves, generates parameters, or bypasses any existing check — it only decides *which* allowlisted action_type to suggest.

Two trigger paths:

- **Automatic**: `hybrid_detection_service.run_for_device` calls it after scoring each window, gated by `self_healing_automation_enabled` (Settings, default **`False`** — off until validated in shadow).
- **Human-triggered**: `POST /hybrid/decisions/{id}/propose-recovery` always works regardless of the flag.

Two Stage-4 companion changes tie into verification: `CompleteCommandRequest`/`CompletionInput` now carry `pre_action_snapshot` (the `recovery_commands.pre_action_snapshot_json` column already existed from Sprint 3 but was never threaded through until now), and `recovery_verification_service.verify()` gained explicit outcomes for `repair_agent_queue`/`repair_local_database` (verified once new telemetry resumes) and `reschedule_sync_workers` (verified once `workers_registered` + fresh telemetry). `scripts/seed_recovery_policies.py` is now self-healing on re-run: it corrects any existing policy row whose `risk_level`/`approval_mode` drifted from the intended value (used to re-tier Android's `enter_safe_monitoring_mode`/`restore_normal_monitoring_mode` from medium/manual to low/auto).

## RBAC & tenant isolation

- `GET /hybrid/decisions*`: all authenticated roles, org-scoped (404-not-403 cross-tenant, same convention as the rest of the API).
- `POST /hybrid/decisions/run`, review, propose-recovery: `admin`/`owner`/`engineer`/`platform_admin`.
- `POST /replay/run`: `admin`/`owner`/`engineer`/`platform_admin` (not org-scoped — replay reasons over feature windows across an entire device class, an internal ML-ops operation).
- Model evaluate/promote/retire: `admin`/`owner`/`platform_admin` only (same tier as the existing model registry view).

## Rollback strategy

Additive, same posture as Sprint 2:

- **Instant kill switches**: `hybrid_detection_enabled`, `historical_replay_enabled`, `self_healing_automation_enabled`.
- **Schema rollback**: each migration documents its own safe `DROP TABLE`/`DROP COLUMN` — zero incoming foreign keys from any pre-existing table into `hybrid_decisions`/`model_evaluation_reports`/`replay_runs`.
- **Code rollback**: `git revert` — no Sprint 1-3 module was modified in a way that changes its own behavior when these new modules are absent (`isolation_forest_service`/`recovery_verification_service`/`seed_recovery_policies` changes are additive branches, not rewrites of existing behavior).

## Tests

`tests/backend/test_hybrid_detection.py` (22), `test_model_lifecycle.py` (18), `test_replay.py` (6) — 46 new tests, all passing alongside the 53 pre-existing tests (99 total). Coverage: detector-agreement/severity/risk pure-function correctness, hybrid pipeline API + RBAC + tenant isolation, promotion gate enforcement (structural + evaluation) at every lifecycle transition, retired-model inference rejection, artifact checksum tampering detection, evaluation report computation, and replay's read-only guarantee (no production table is ever written to) plus export formats.
