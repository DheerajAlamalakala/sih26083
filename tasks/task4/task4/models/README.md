# Task 4 — Models

`train_models.py` fits and saves both models here:
- `daily_mortality_<MODEL_VERSION>.joblib`
- `daily_hospitalizations_<MODEL_VERSION>.joblib`
- `<MODEL_VERSION>_metadata.json` — training timestamp, sample sizes,
  val/test metrics (with an explicit warning attached given the
  current sample size), and a `calibration` section: the per-target
  risk-score saturation point, computed once from the training set.

`predict.py` only loads these — it does not train, and it does not
recompute calibration. If no saved model is found for the current
`MODEL_VERSION` (see `baseline_risk.py`), or the metadata file has no
`calibration` section, it raises rather than silently retraining or
recalibrating on whatever batch it was just given. (v1_1 recomputed
calibration per inference call from that call's own batch, which
meant the same ward-day could score differently depending on what
else was being scored alongside it — fixed in v1_2.)

**Retrain whenever new labeled data lands**:
```bash
python3 -m src.health.train_models
```
Bump `MODEL_VERSION` in `baseline_risk.py` first if the retrain
reflects a meaningfully different dataset (e.g. full 155-ward data
instead of the current 2-ward demo) so old predictions stay
traceable to the model that produced them.
