import pytest
from src.alerts.action_engine import create_action_record


def test_low_alert():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=20,
        hospitalization_risk_0_100=15,
        vulnerability_0_100=20,
        heat_persistence_hours=12
    )

    assert result.alert_level == "LOW"


def test_moderate_alert():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=45,
        hospitalization_risk_0_100=40,
        vulnerability_0_100=40,
        heat_persistence_hours=12
    )

    assert result.alert_level == "MODERATE"


def test_high_alert():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=72,
        hospitalization_risk_0_100=68,
        vulnerability_0_100=65,
        heat_persistence_hours=12
    )

    assert result.alert_level == "HIGH"


def test_critical_alert():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=90,
        hospitalization_risk_0_100=85,
        vulnerability_0_100=90,
        heat_persistence_hours=12
    )

    assert result.alert_level == "CRITICAL"


def test_alert_boundary():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=30,
        hospitalization_risk_0_100=30,
        vulnerability_0_100=30,
        heat_persistence_hours=0
    )

    assert result.alert_level == "LOW"

def test_moderate_boundary():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=60,
        hospitalization_risk_0_100=60,
        vulnerability_0_100=60,
        heat_persistence_hours=0
    )

    assert result.alert_level == "MODERATE"


def test_high_boundary():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=80,
        hospitalization_risk_0_100=80,
        vulnerability_0_100=80,
        heat_persistence_hours=0
    )

    assert result.alert_level == "HIGH"


def test_critical_boundary():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=100,
        hospitalization_risk_0_100=100,
        vulnerability_0_100=100,
        heat_persistence_hours=0
    )

    assert result.alert_level == "CRITICAL"

def test_invalid_risk_value():
    with pytest.raises(ValueError):
        create_action_record(
            ward_id="WARD_001",
            valid_time_utc="2026-09-23T12:00:00Z",
            forecast_day=1,
            mortality_risk_0_100=120,
            hospitalization_risk_0_100=80,
            vulnerability_0_100=50,
            heat_persistence_hours=0
        )

def test_high_alert_actions():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=72,
        hospitalization_risk_0_100=68,
        vulnerability_0_100=65,
        heat_persistence_hours=12
    )

    assert result.alert_level == "HIGH"
    assert result.advisory_id == "ADV_HIGH_01"
    assert result.notification_required is True
    assert result.notification_status == "queued"

    assert "Prepare or open cooling centres" in result.municipal_actions
    assert "Increase healthcare preparedness" in result.municipal_actions
    assert "Prepare for increased power demand" in result.municipal_actions
    assert "Consider shifting outdoor work hours" in result.municipal_actions

def test_invalid_forecast_day():
    with pytest.raises(ValueError):
        create_action_record(
            ward_id="WARD_001",
            valid_time_utc="2026-09-23T12:00:00Z",
            forecast_day=6,
            mortality_risk_0_100=50,
            hospitalization_risk_0_100=45,
            vulnerability_0_100=50,
            heat_persistence_hours=0
        )

def test_quality_flag():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=50,
        hospitalization_risk_0_100=45,
        vulnerability_0_100=50,
        heat_persistence_hours=0
    )

    assert result.quality_flag == "VALID"    

def test_low_alert_actions():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=20,
        hospitalization_risk_0_100=15,
        vulnerability_0_100=20,
        heat_persistence_hours=0
    )

    assert result.alert_level == "LOW"
    assert result.advisory_id == "ADV_LOW_01"
    assert result.notification_required is False


def test_moderate_alert_actions():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=45,
        hospitalization_risk_0_100=40,
        vulnerability_0_100=40,
        heat_persistence_hours=0
    )

    assert result.alert_level == "MODERATE"
    assert result.advisory_id == "ADV_MODERATE_01"
    assert result.notification_required is True


def test_high_alert_actions():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=72,
        hospitalization_risk_0_100=68,
        vulnerability_0_100=65,
        heat_persistence_hours=12
    )

    assert result.alert_level == "HIGH"
    assert result.advisory_id == "ADV_HIGH_01"
    assert result.notification_required is True


def test_critical_alert_actions():
    result = create_action_record(
        ward_id="WARD_001",
        valid_time_utc="2026-09-23T12:00:00Z",
        forecast_day=1,
        mortality_risk_0_100=90,
        hospitalization_risk_0_100=85,
        vulnerability_0_100=90,
        heat_persistence_hours=12
    )

    assert result.alert_level == "CRITICAL"
    assert result.advisory_id == "ADV_CRITICAL_01"
    assert result.notification_required is True