# Synthetic health outcomes — Task 4

`health_outcomes_demo.csv` contains **synthetic** daily mortality and
hospitalization counts. They are NOT observed medical records.

- Generated from real Stage 1 (`thermal_stress_0_100`) and Task 3
  (`vulnerability_0_100`) values only — no independent weather/WBGT
  was invented for this step.
- Distribution: Poisson, rate is a nonlinear (log-linear) function of
  thermal stress, vulnerability, heat persistence, and seasonality.
- Every row is tagged `is_synthetic=True`, `source_type=synthetic_demo`,
  `synthetic_generation_version=v1_0`.
- Any model trained on this data is a **demonstration of the pipeline
  only** and must not be presented as having clinical or epidemiological
  validity. If real, legally-obtained health data becomes available,
  swap it in and rerun the same pipeline with `source_type=real_public`.
