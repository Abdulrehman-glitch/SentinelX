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
