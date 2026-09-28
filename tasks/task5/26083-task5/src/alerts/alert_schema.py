class WardActionRecord:
    def __init__(
        self,
        ward_id,
        valid_time_utc,
        forecast_day,
        alert_level,
        advisory_id,
        advisory_text,
        municipal_actions,
        notification_required,
        notification_status,
        rule_version,
        quality_flag
    ):
        self.ward_id = ward_id
        self.valid_time_utc = valid_time_utc
        self.forecast_day = forecast_day
        self.alert_level = alert_level
        self.advisory_id = advisory_id
        self.advisory_text = advisory_text
        self.municipal_actions = municipal_actions
        self.notification_required = notification_required
        self.notification_status = notification_status
        self.rule_version = rule_version
        self.quality_flag = quality_flag