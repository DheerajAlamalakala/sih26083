from .alert_schema import WardActionRecord
from .action_rules import load_action_rules, get_alert_level, get_alert_details


def create_action_record(
    ward_id,
    valid_time_utc,
    forecast_day,
    mortality_risk_0_100,
    hospitalization_risk_0_100,
    vulnerability_0_100,
    heat_persistence_hours
):
    action_rules = load_action_rules()
    # Validate risk values.
    if not 0 <= mortality_risk_0_100 <= 100:
        raise ValueError("mortality_risk_0_100 must be between 0 and 100")

    if not 0 <= hospitalization_risk_0_100 <= 100:
        raise ValueError("hospitalization_risk_0_100 must be between 0 and 100")

    if not 0 <= vulnerability_0_100 <= 100:
        raise ValueError("vulnerability_0_100 must be between 0 and 100")

     # Validate forecast day.
    if not 1 <= forecast_day <= 5:
        raise ValueError("forecast_day must be between 1 and 5")
    
    # Get the higher health-risk value from Task 4.
    health_risk = max(
        mortality_risk_0_100,
        hospitalization_risk_0_100
    )

    # PROJECT-DEFINED PROTOTYPE RULE:
    # A prolonged heat condition adds a small action-risk adjustment.
    # This is temporary and can be replaced later
    # with the validated methodology.

    persistence_adjustment = 0

    if heat_persistence_hours >= 12:
        persistence_adjustment = 5

    # PROJECT-DEFINED PROTOTYPE RULE:
    # 70% health risk + 30% vulnerability + persistence adjustment.
    #
    # IMPORTANT:
    # This does NOT modify the original
    # mortality_risk_0_100 or hospitalization_risk_0_100
    # values from Task 4.

    action_risk_0_100 = (
        (health_risk * 0.70)
        + (vulnerability_0_100 * 0.30)
        + persistence_adjustment
    )

    alert_level = get_alert_level(
        action_risk_0_100,
        action_rules
    )

    alert_details = get_alert_details(
        alert_level,
        action_rules
    )

    # Canonical notification_status values per the Playbook contract are
    # queued/sent/simulated/not_required — never a non-canonical value
    # such as "PENDING". This module only decides an alert level; it does
    # not itself dispatch notifications, so a ward that requires
    # notification is queued for the delivery step (Task 6 / notification
    # provider) and a ward that does not require one is not_required.
    notification_status = "queued" if alert_details["notification_required"] else "not_required"

    action_record = WardActionRecord(
        ward_id=ward_id,
        valid_time_utc=valid_time_utc,
        forecast_day=forecast_day,
        alert_level=alert_level,
        advisory_id=alert_details["advisory_id"],
        advisory_text=alert_details["advisory_text"]["en"],
        municipal_actions=alert_details["municipal_actions"],
        notification_required=alert_details["notification_required"],
        notification_status=notification_status,
        rule_version=action_rules["rule_version"],
        quality_flag="VALID"
    )

    return action_record