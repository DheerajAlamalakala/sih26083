import json
from src.health.train_models import run_training
from src.health.baseline_risk import MODEL_VERSION


def test_run_training_persists_calibration(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    metadata = run_training(
        "data/processed/thermal/stage1_output.csv",
        "data/processed/vulnerability/ward_vulnerability.csv",
        models_dir=str(models_dir),
    )

    assert "calibration" in metadata
    assert set(metadata["calibration"].keys()) == {"daily_mortality", "daily_hospitalizations"}
    assert all(v > 0 for v in metadata["calibration"].values())

    # Metadata written to disk must match what run_training() returned —
    # predict.py reads it back from disk, not from the in-memory dict.
    with open(models_dir / f"{MODEL_VERSION}_metadata.json") as f:
        on_disk = json.load(f)
    assert on_disk["calibration"] == metadata["calibration"]

    for target in ("daily_mortality", "daily_hospitalizations"):
        assert (models_dir / f"{target}_{MODEL_VERSION}.joblib").exists()
