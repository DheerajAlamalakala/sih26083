# Task 4 — Health Risk Model (Stage 2)

## v1_2 — scoped fixes from a second external review
A second review of v1_1 confirmed the architecture and acceptance
criteria were sound, but flagged that several items in a proposed
32-section "complete Task 4" prompt could not honestly be satisfied
by any code change — they require historical data, a real forecast
feed, or population data that don't exist yet (see "Known limitations
still open" below; that's unchanged from v1_1). Separately, it
flagged real, fixable bugs in the current code. This version fixes
those:

1. **Calibration is now computed once, at training time, and
   persisted** in `models/<MODEL_VERSION>_metadata.json` under
   `calibration`. v1_1 recomputed the risk-score saturation point
   from whatever rows happened to be in the *inference* batch, which
   meant the same ward-day could score differently depending on what
   else was being scored alongside it in that call. `predict.py` now
   only loads this value (`load_calibration()`) and raises if it's
   missing — it never recalculates it.
2. **`forecast_issued_at_utc` added to the `HealthRiskRecord`
   schema.** Always `null` for now: Task 1 has no real forecast-issue
   timestamp yet, and `forecast_day` is still a historical-window
   index (see below), not a genuine horizon. Adding the field now
   means Task 5/6 don't need a breaking schema change once Task 1
   delivers real forecast issuance.
3. **Vulnerability file must have exactly one row per `ward_id`.**
   New `data_quality.py` raises `DataQualityError` if it doesn't —
   two rows for one ward would silently duplicate every Stage 1 hour
   for that ward on the join, which is worse than failing loudly.
4. **Stage 1 hourly-coverage validation.** The same module reports
   malformed timestamps, duplicate `(ward_id, timestamp)` rows, and
   per-ward gaps in hourly coverage. `feature_builder.load_stage1()`
   now drops duplicate timestamp rows (flagging them
   `DUPLICATE_STAGE1_TIMESTAMP_DROPPED`) instead of silently
   double-counting them into the rolling heat-persistence window and
   the daily aggregation.
5. **Fixed a duplicate-quality-flag-token bug found while doing the
   above.** The daily aggregation merged hourly `quality_flag` values
   by deduping whole per-row strings, not tokens — so 24 hourly rows
   each carrying e.g. `"OK|NO_VULNERABILITY_MATCH"` could produce a
   daily flag with `NO_VULNERABILITY_MATCH` repeated many times over.
   A second instance of the same bug had `aggregate_to_daily`
   unconditionally re-appending that flag even when it was already
   present from the hourly level. Both fixed; flags are now deduped
   at the token level.
6. **Stricter split test**: no calendar date may appear in more than
   one of train/validation/test (stronger than just checking the
   split boundaries, which doesn't rule out a tie landing in two
   splits).
7. **Test proving inference never trains**: `PoissonRegressor.fit` is
   monkeypatched to raise, and the full `predict_health_risk()` path
   is run successfully against it.

`MODEL_VERSION` bumped to `baseline_poisson_v1_2` since calibration's
source changed — old predictions stay traceable to the code that
produced them.

## v1_1 — post-review revision
A review of v1_0 caught a real bug: synthetic health labels were
generated on **hourly** Stage-1 rows and stamped `daily_mortality`,
producing ~24 conflicting "daily" values per ward-day. That inflated
the apparent sample size (194/48 "rows") and made the model appear
better-supported than it was. This version fixes that and several
related issues — see "What changed in v1_1" below.

## ⚠️ Synthetic data disclaimer (read before demoing or presenting)
**No suitable real, ward-level, public mortality/hospitalization
dataset was available for this problem statement.** All health
outcome labels are **synthetically generated** from Stage 1 thermal
stress + Task 3 vulnerability, via a Poisson count model with a
nonlinear rate function of thermal stress, vulnerability, heat
persistence, and seasonality.

- Every synthetic row is tagged `is_synthetic=True`,
  `source_type=synthetic_demo`, `synthetic_generation_version=v1_1`.
- **This model has no clinical or epidemiological validity.** It
  demonstrates that the pipeline works end to end, not that it
  predicts real health outcomes.
- The model is trained to reproduce the same synthetic relationship
  used to generate its own labels — this is inherent to any
  synthetic-label demo, not something a smarter model avoids. It
  proves the pipeline is wired correctly, nothing more.

## What changed in v1_1 (fixes to real bugs, not just re-documentation)
1. **Daily granularity, for real.** Stage-1 hourly rows are now
   aggregated to one row per (ward_id, date) — `daily_aggregation.py`
   — *before* synthetic labels are generated. One label per ward-day.
2. **Missing vulnerability is never zero-filled.** Rows with no
   vulnerability match get a `NaN` label (`generate_synthetic_health`)
   and are excluded from training (`drop_unlabeled`), never treated as
   "zero vulnerability."
3. **Train/validation/test**, not train/test — `time_based_split()`
   returns three chronological slices.
4. **Training and inference are separate.** `train_models.py` fits and
   saves models (`models/*.joblib` + metadata JSON); `predict.py` only
   loads them. It no longer retrains on the same data it predicts on.
5. **Drivers are computed per-target.** Mortality and hospitalization
   each get their own top-3 driver list from their own model, instead
   of hospitalization output reusing mortality's drivers.
6. **Risk score calibration is model-relative**, not an arbitrary fixed
   constant — the 0–100 saturation point is set from the model's own
   predicted-rate distribution (90th percentile on labeled data), so a
   below-average day reads low and an above-average day reads high
   relative to what the model has actually seen. Still a
   project-defined scale, not a clinical probability.

## Honest result of the fix
Correcting the granularity bug drops the labeled sample from a
misleading "194 train / 48 test" (hourly pseudo-rows) down to its real
size: **10 labeled ward-days** (6 train / 2 val / 2 test). Test-set
Poisson deviance on 2 points is essentially noise — one fold showed a
mortality deviance in the thousands. This is not a new regression;
it's the honest picture that the bug had been hiding. Do not present
current metrics as evidence of model skill under any circumstance.

## Pipeline
```
Stage 1 (hourly ThermalStressRecord) ─┐
                                        ├─▶ feature_builder.py ─▶ daily_aggregation.py
Task 3 (vulnerability.csv) ────────────┘                              │
                                                                        ▼
                                                     generate_synthetic_health.py (daily)
                                                                        │
                                                                        ▼
                                                    train_models.py ──▶ models/*.joblib
                                                                        │
                                                                        ▼
                                                        predict.py ──▶ HealthRiskRecord
```

## Known limitations still open (not code bugs — need team/data action)
- **Sample size**: 2 real wards × 5 days = 10 ward-days. Too small for
  any real skill estimate. Needs Task 2 to rerun Stage 1 across all
  155 wards over a multi-week/seasonal window.
- **`forecast_day` is not a real forecast horizon.** It's "day N of
  the historical window we have," flagged `FORECAST_DAY_APPROXIMATED`.
  Needs Task 1 to supply genuine multi-day-ahead weather forecasts.
- **Ward mapping is an unconfirmed guess**
  (`HYD_W001→GHMC_W001` in `ward_id_bridge.py`). Confirm with Task 2's
  owner or get them to emit canonical `GHMC_Wxxx` IDs directly.
- **Only 6 of Stage 1's fields feed the model**
  (`thermal_stress_mean/max`, `vulnerability_0_100`,
  `heat_persistence_hours`, `doy_sin/cos`). WBGT, UTCI, heat index,
  and raw temperature/humidity/wind/radiation are available from
  Stage 1 but not yet used as separate features — worth testing once
  there's enough data to support more parameters without overfitting.
- **`elderly_exposure_0_100` / `outdoor_worker_exposure_0_100`** from
  Task 3 are not used directly, only via the combined
  `vulnerability_0_100`. Fine if that's an intentional aggregate;
  document the combination if so.
- **No uncertainty quantification** on risk scores — a point estimate
  with no confidence interval. Not required by the playbook, but
  would be a meaningful addition given how thin the training data is.
- **No baseline-vs-baseline comparison** (e.g., against a naive
  seasonal/persistence baseline) to show the Poisson model adds value
  over doing nothing clever.

## Integration contract for Task 5
`predict.py` → `predict_health_risk(stage1_path, vulnerability_path, models_dir="models")`
returns one row per (ward_id, forecast_day):

`ward_id, valid_time_utc, forecast_day, forecast_issued_at_utc,
thermal_stress_mean, vulnerability_0_100, mortality_risk_0_100,
hospitalization_risk_0_100, mortality_risk_level,
hospitalization_risk_level, mortality_drivers, hospitalization_drivers,
is_synthetic, source_type, model_version, quality_flag`

`forecast_issued_at_utc` is always `null` today — see "What changed
in v1_2" above. Task 5 should not treat its presence in the schema as
evidence that real forecast issuance exists yet.

Task 5 must treat any row with `NaN` risk scores / `risk_level="unknown"`
(flagged `INSUFFICIENT_DATA_FOR_PREDICTION`) as **not actionable** —
don't alert on it as if it were a real prediction. Also treat
`FORECAST_DAY_APPROXIMATED` rows as lower-confidence than a genuine
forecast would be.

**Before retraining**: run `python3 -m src.health.train_models` after
any new labeled data lands. This is the only place model fitting (and
calibration) happens — `predict.py` will refuse to run (raises
`FileNotFoundError`) if no saved model or no persisted calibration
exists, rather than silently retraining or recalibrating on whatever's
passed to it.
