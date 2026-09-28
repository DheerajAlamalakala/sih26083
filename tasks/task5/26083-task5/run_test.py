import json

from src.alerts.action_engine import create_action_record


# Read the sample Task 4 health-risk record
with open("sample/sample_health_risk.json", "r") as file:
    health_risk_data = json.load(file)


result = create_action_record(
    ward_id=health_risk_data["ward_id"],
    valid_time_utc=health_risk_data["valid_time_utc"],
    forecast_day=health_risk_data["forecast_day"],
    mortality_risk_0_100=health_risk_data["mortality_risk_0_100"],
    hospitalization_risk_0_100=health_risk_data["hospitalization_risk_0_100"],
    vulnerability_0_100=health_risk_data["vulnerability_0_100"],
    heat_persistence_hours=12
)


output = {
    "ward_id": result.ward_id,
    "valid_time_utc": result.valid_time_utc,
    "forecast_day": result.forecast_day,
    "alert_level": result.alert_level,
    "advisory_id": result.advisory_id,
    "advisory_text": result.advisory_text,
    "municipal_actions": result.municipal_actions,
    "notification_required": result.notification_required,
    "notification_status": result.notification_status,
    "rule_version": result.rule_version,
    "quality_flag": result.quality_flag
}


with open("sample/stage3_ward_action_record.json", "w") as file:
    json.dump(output, file, indent=4)


print("Stage 3 WardActionRecord created successfully.")