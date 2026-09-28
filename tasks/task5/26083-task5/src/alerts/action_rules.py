import json
import os


def load_action_rules():
    current_folder = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_folder, "advisories.json")

    with open(config_path, "r") as file:
        return json.load(file)


def get_alert_level(risk_value, action_rules):
    alert_levels = action_rules["alert_levels"]

    for alert_level, rules in alert_levels.items():
        minimum_risk = rules["minimum_risk"]
        maximum_risk = rules["maximum_risk"]

        if alert_level == "LOW":
            if minimum_risk <= risk_value <= maximum_risk:
                return alert_level
        else:
            if minimum_risk < risk_value <= maximum_risk:
                return alert_level

    raise ValueError("Risk value must be between 0 and 100")


def get_alert_details(alert_level, action_rules):
    return action_rules["alert_levels"][alert_level]