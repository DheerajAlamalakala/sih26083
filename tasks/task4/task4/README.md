# Task 4 — Stage 2 Health Impact Prediction (SIH 26083)

Consumes Task 2's Stage-1 thermal stress + Task 3's ward vulnerability,
predicts mortality/hospitalization risk (Day+1 to +5), outputs the
canonical `HealthRiskRecord` schema for Task 5.

**Read `docs/science/health_risk_model.md` first.** It has the
synthetic-data disclaimer, what was fixed in v1_1 and v1_2 after
external review, the honest (small) sample size, and the integration
contract for Task 5.

## Quick start
```bash
pip install -r requirements.txt
export PYTHONPATH=.
python3 -m src.health.train_models   # trains + saves models/*.joblib + calibration (do this first)
python3 src/health/predict.py        # loads saved models + calibration, writes sample/stage2_health_risk_output.csv
python3 -m pytest tests/ -q          # 40 tests
jupyter notebook notebooks/01_health_risk_baseline.ipynb
```

## Layout
```
src/health/
  ward_id_bridge.py           # demo/real ward_id mismatch bridge (mapping unconfirmed — see doc)
  data_quality.py             # vulnerability-uniqueness + Stage-1 hourly-coverage validation
  feature_builder.py          # joins Stage 1 + vulnerability (hourly), runs data_quality checks
  daily_aggregation.py        # hourly -> one row per ward-day (fixes the v1_0 granularity bug)
  generate_synthetic_health.py# synthetic daily labels; NaN vuln -> NaN label, never zero
  baseline_risk.py            # Poisson models, train/val/test split, calibration
  mortality_model.py          # named wrapper (playbook file layout)
  hospitalization_model.py    # named wrapper (playbook file layout)
  train_models.py             # ONLY place models are fit; saves models/*.joblib + calibration
  predict.py                  # inference only; loads saved models + calibration -> HealthRiskRecord
scripts/generate_synthetic_health.py   # CLI entry point
data/synthetic/                        # synthetic labels + disclaimer README
models/                                 # saved model artifacts + metadata (incl. calibration) + README
docs/science/health_risk_model.md      # full write-up, READ FIRST
notebooks/01_health_risk_baseline.ipynb
tests/                                  # 40 tests, all passing
sample/stage2_health_risk_output.csv    # example output
```

## Before final demo/submission — flag these to the team
1. Confirm the `HYD_W001→GHMC_W001` ward mapping with Task 2's owner (currently a guess).
2. Get Task 2 to rerun Stage 1 across all 155 real wards, over weeks not days — current sample is 10 labeled ward-days total, too small for a real skill estimate.
3. `forecast_day` is currently a historical-day stand-in, not a true forecast horizon — needs Task 1's real multi-day forecast to fix properly.
4. Consider adding WBGT/UTCI/heat-index and elderly/outdoor-worker exposure as separate model features once there's enough data to support them without overfitting.
