import pandas as pd
from src.health.daily_aggregation import aggregate_to_daily, NO_VULN_FLAG

def _toy_hourly():
    ts = pd.to_datetime(
        ["2026-05-10T00:00:00Z", "2026-05-10T12:00:00Z", "2026-05-10T23:00:00Z",
         "2026-05-11T00:00:00Z"], utc=True
    )
    return pd.DataFrame({
        "ward_id": ["W1", "W1", "W1", "W1"],
        "timestamp_utc": ts,
        "thermal_stress_0_100": [40.0, 80.0, 60.0, 50.0],
        "heat_persistence_hours": [1.0, 5.0, 8.0, 1.0],
        "doy_sin": [0.1, 0.1, 0.1, 0.2],
        "doy_cos": [0.9, 0.9, 0.9, 0.8],
        "vulnerability_0_100": [55.0, 55.0, 55.0, 55.0],
        "quality_flag": ["OK", "OK", "OK", "OK"],
    })

def test_one_row_per_ward_day():
    daily = aggregate_to_daily(_toy_hourly())
    assert len(daily) == 2  # 2026-05-10 and 2026-05-11
    assert set(daily["date"].astype(str)) == {"2026-05-10", "2026-05-11"}

def test_thermal_stress_aggregated_not_passed_through_raw():
    daily = aggregate_to_daily(_toy_hourly())
    day1 = daily[daily["date"].astype(str) == "2026-05-10"].iloc[0]
    assert day1["thermal_stress_mean"] == (40.0 + 80.0 + 60.0) / 3
    assert day1["thermal_stress_max"] == 80.0

def test_missing_vulnerability_stays_nan_not_zero():
    hourly = _toy_hourly()
    hourly["vulnerability_0_100"] = None
    daily = aggregate_to_daily(hourly)
    assert daily["vulnerability_0_100"].isna().all()
    assert daily["quality_flag"].str.contains(NO_VULN_FLAG).all()


def test_missing_vulnerability_flag_not_duplicated_if_already_present():
    # feature_builder already stamps NO_VULNERABILITY_MATCH per-hour when
    # the vulnerability join misses. aggregate_to_daily must not append
    # the same token a second time on top of that.
    hourly = _toy_hourly()
    hourly["vulnerability_0_100"] = None
    hourly["quality_flag"] = f"OK|{NO_VULN_FLAG}"
    daily = aggregate_to_daily(hourly)
    for flag in daily["quality_flag"]:
        tokens = flag.split("|")
        assert tokens.count(NO_VULN_FLAG) == 1


def test_quality_flag_tokens_deduped_not_repeated_across_hours():
    # Every hourly row already carries a compound flag ("OK|X"). Naively
    # deduping whole strings (as v1_1 did) leaves "OK" repeated once per
    # distinct compound string that contains it. Deduping must happen at
    # the token level so a daily flag never repeats the same token.
    hourly = _toy_hourly()
    hourly["quality_flag"] = ["OK|WARD_ID_UNMATCHED", "OK|NO_VULNERABILITY_MATCH", "OK", "OK"]
    daily = aggregate_to_daily(hourly)
    day1_flag = daily[daily["date"].astype(str) == "2026-05-10"].iloc[0]["quality_flag"]
    tokens = day1_flag.split("|")
    assert len(tokens) == len(set(tokens))
    assert tokens.count("OK") == 1
