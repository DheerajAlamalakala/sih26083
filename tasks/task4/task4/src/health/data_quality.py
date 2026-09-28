"""
Task 4 — data-quality validation for Task 2 (Stage 1 thermal) and
Task 3 (vulnerability) handoffs.

Per the playbook's integration handoff checklist: "Task 3 -> Task 4:
vulnerability is joined by the same ward_id. Missing joins must be
visible in quality_flag." This module makes join-readiness problems
visible (or fails loudly where silently continuing would corrupt
downstream data) BEFORE the join happens, rather than discovering
them as unexplained row-count drift after aggregation.

Nothing here recomputes WBGT/UTCI/HI, vulnerability scores, or any
other upstream science — it only inspects the SHAPE of what Task 2
and Task 3 handed off.
"""
from __future__ import annotations
import pandas as pd


class DataQualityError(ValueError):
    """Raised when continuing would silently corrupt or double-count
    data (e.g. two conflicting vulnerability rows for one ward). This
    is deliberately NOT a quality_flag situation — a quality_flag can
    mark a single row as low-confidence, but it can't undo a join that
    silently fanned out because the join key wasn't unique."""


def validate_vulnerability_uniqueness(vuln: pd.DataFrame, ward_col: str = "ward_id") -> None:
    """Task 3's vulnerability file must have exactly one row per
    ward_id. Two rows for the same ward would silently duplicate every
    Stage 1 hour for that ward on a left-join — worse than failing
    loudly, and easy to miss in a 155-ward file.
    """
    dupes = vuln[ward_col][vuln[ward_col].duplicated(keep=False)]
    if not dupes.empty:
        offending = sorted(dupes.unique().tolist())
        raise DataQualityError(
            f"Vulnerability file has {len(offending)} ward_id(s) with more than "
            f"one row: {offending}. Fix at source (Task 3) — Task 4 must not "
            f"silently pick one row and drop the rest."
        )


def check_stage1_hourly_coverage(stage1: pd.DataFrame, ward_col: str = "ward_id",
                                  timestamp_col: str = "timestamp_utc") -> dict:
    """Report-only (never raises) coverage check on Task 2's Stage 1
    output: malformed timestamps, duplicate (ward_id, timestamp) rows,
    and per-ward gaps in the expected hourly cadence. Callers decide
    what to do with the report (e.g. feature_builder drops exact
    duplicate rows and logs a warning; it does not fail the whole
    pipeline on a gap, since gaps are expected in the current 5-day
    demo fixture and are already visible via quality_flag downstream).
    """
    parsed = pd.to_datetime(stage1[timestamp_col], utc=True, errors="coerce")
    malformed_count = int(parsed.isna().sum() - stage1[timestamp_col].isna().sum())

    working = stage1.assign(_parsed_ts=parsed).dropna(subset=["_parsed_ts"])
    dup_mask = working.duplicated(subset=[ward_col, "_parsed_ts"], keep=False)
    duplicate_row_count = int(dup_mask.sum())

    missing_hours_by_ward: dict[str, float] = {}
    for ward_id, group in working.sort_values("_parsed_ts").groupby(ward_col):
        ts = group["_parsed_ts"].drop_duplicates().sort_values()
        if len(ts) < 2:
            continue
        gap_hours = ts.diff().dropna().dt.total_seconds() / 3600.0
        total_gap = gap_hours[gap_hours > 1.0].sub(1.0).sum()  # hours missing, not hours between readings
        if total_gap > 0:
            missing_hours_by_ward[str(ward_id)] = float(total_gap)

    return {
        "malformed_timestamp_count": malformed_count,
        "duplicate_timestamp_row_count": duplicate_row_count,
        "missing_hours_by_ward": missing_hours_by_ward,
    }
