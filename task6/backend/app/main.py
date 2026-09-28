
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from twilio.rest import Client as TwilioClient
except ImportError:  # Optional until Twilio is configured/installed.
    TwilioClient = None

from .data import (
    build_action_records,
    load_health_risk,
    load_vulnerability,
    load_wards,
    load_weather_fixture,
)

app = FastAPI(
    title="SIH 26083 Extreme Heatwave Early Warning System",
    version="1.0.0-demo",
    description="Task 6 integration layer over canonical Task 1/3/4/5 artifacts.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEALTH = load_health_risk()
VULNERABILITY = load_vulnerability()
WARD_GEOJSON = load_wards()
WEATHER = load_weather_fixture()
ACTIONS = build_action_records(HEALTH, VULNERABILITY)
NOTIFICATION_LOG: list[dict[str, Any]] = []


class TriggerRequest(BaseModel):
    ward_id: str
    forecast_day: int = Field(ge=1, le=5)


class NotificationRequest(BaseModel):
    ward_id: str
    channel: str = "sms"
    recipient_role: str = "municipal_ward_officer"
    message: str | None = None


RECIPIENT_ROLES = {
    "municipal_ward_officer": {
        "label": "Municipal / Ward Officer",
        "env": "RAKSHA_MUNICIPAL_WARD_OFFICER_PHONE",
    },
    "disaster_management": {
        "label": "Disaster Management Control Room",
        "env": "RAKSHA_DISASTER_MANAGEMENT_PHONE",
    },
    "health_coordination": {
        "label": "Health Coordination Officer",
        "env": "RAKSHA_HEALTH_COORDINATION_PHONE",
    },
}

def _twilio_config() -> dict[str, Any]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    trial_mode = os.getenv("RAKSHA_TWILIO_TRIAL_MODE", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }
    trial_template = os.getenv("RAKSHA_TWILIO_TRIAL_TEMPLATE", "sms_internal_alerts").strip()
    return {
        "configured": bool(account_sid and auth_token and from_number and TwilioClient),
        "account_sid": account_sid,
        "auth_token": auth_token,
        "from_number": from_number,
        "trial_mode": trial_mode,
        "trial_template": trial_template or "sms_internal_alerts",
    }

def _recipient_status() -> list[dict[str, Any]]:
    return [
        {
            "role": role,
            "label": meta["label"],
            "configured": bool(os.getenv(meta["env"], "").strip()),
        }
        for role, meta in RECIPIENT_ROLES.items()
    ]


@app.get("/api/v1/notifications/config")
def notification_config() -> dict[str, Any]:
    twilio = _twilio_config()
    return {
        "provider": "Twilio",
        "sms_configured": twilio["configured"],
        "recipient_roles": _recipient_status(),
        "mode": "trial" if twilio["configured"] and twilio["trial_mode"] else ("live" if twilio["configured"] else "not_configured"),
        "trial_mode": twilio["trial_mode"],
        "trial_template": twilio["trial_template"],
    }


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "offline_demo",
        "datasets": {
            "health_risk": len(HEALTH),
            "vulnerability_wards": len(VULNERABILITY),
            "mapped_geometry_wards": len(WARD_GEOJSON["features"]),
        },
    }


@app.get("/api/v1/forecast")
def forecast(
    ward_id: str | None = None,
    forecast_day: int | None = Query(default=None, ge=1, le=5),
) -> dict[str, Any]:
    rows = HEALTH
    if ward_id:
        rows = [r for r in rows if r["ward_id"] == ward_id]
    if forecast_day:
        rows = [r for r in rows if r["forecast_day"] == forecast_day]
    return {"mode": "offline_demo", "records": rows}


@app.get("/api/v1/wards")
def wards() -> dict[str, Any]:
    return WARD_GEOJSON


@app.get("/api/v1/wards/risk")
def wards_risk(date: str | None = None) -> list[dict[str, Any]]:
    rows = HEALTH
    if date:
        rows = [r for r in rows if r["valid_time_utc"][:10] == date]
    latest = {}
    for row in rows:
        latest[row["ward_id"]] = row
    return [
        {
            **VULNERABILITY.get(ward_id, {"ward_id": ward_id}),
            "health_risk": row,
        }
        for ward_id, row in latest.items()
    ]


@app.get("/api/v1/wards/{ward_id}")
def ward_detail(ward_id: str) -> dict[str, Any]:
    if ward_id not in VULNERABILITY:
        raise HTTPException(status_code=404, detail="ward_id not found")
    return {
        "ward": VULNERABILITY[ward_id],
        "forecast": [r for r in HEALTH if r["ward_id"] == ward_id],
        "actions": [a for a in ACTIONS if a["ward_id"] == ward_id],
    }


@app.get("/api/v1/alerts")
def alerts(
    alert_level: str | None = None,
    ward_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = ACTIONS
    if alert_level:
        rows = [r for r in rows if r["alert_level"].upper() == alert_level.upper()]
    if ward_id:
        rows = [r for r in rows if r["ward_id"] == ward_id]
    return rows


@app.post("/api/v1/actions/trigger")
def trigger_action(request: TriggerRequest) -> dict[str, Any]:
    matches = [
        a for a in ACTIONS
        if a["ward_id"] == request.ward_id and a["forecast_day"] == request.forecast_day
    ]
    if not matches:
        raise HTTPException(status_code=404, detail="No canonical action record available")
    return {"status": "available", "action": matches[0], "source": "task5_action_engine"}


@app.post("/api/v1/notifications/send")
def send_notification(request: NotificationRequest) -> dict[str, Any]:
    actions = [
        a for a in ACTIONS
        if a["ward_id"] == request.ward_id
    ]
    if not actions:
        raise HTTPException(status_code=404, detail="ward_id not found")

    channel = request.channel.lower()
    if channel not in {"sms", "whatsapp", "simulated"}:
        raise HTTPException(status_code=400, detail="Unsupported notification channel")

    action = actions[0]
    role = RECIPIENT_ROLES.get(request.recipient_role)
    if not role:
        raise HTTPException(status_code=400, detail="Unknown recipient role")

    recipient = os.getenv(role["env"], "").strip()
    body = request.message or (
        f"RAKSHA HEAT ALERT — {action['alert_level']}\n"
        f"Ward: {action['ward_id']} | Forecast Day: {action['forecast_day']}\n"
        f"Advisory: {action['advisory_text']}"
    )

    if channel == "simulated":
        entry = {
            "ward_id": request.ward_id,
            "channel": channel,
            "status": "simulated",
            "recipient_role": request.recipient_role,
            "recipient_label": role["label"],
            "message": body,
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "demo_only": True,
        }
        NOTIFICATION_LOG.append(entry)
        return entry

    if channel != "sms":
        raise HTTPException(
            status_code=501,
            detail="WhatsApp remains available as a future Twilio channel; real SMS is enabled in this build.",
        )

    twilio = _twilio_config()
    if not twilio["configured"]:
        raise HTTPException(
            status_code=503,
            detail="Twilio SMS is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER and the selected recipient phone environment variable.",
        )
    if not recipient:
        raise HTTPException(
            status_code=503,
            detail=f"No phone number is configured for {role['label']}. Set {role['env']} in the backend environment.",
        )

    # Twilio trial accounts do not accept arbitrary SMS bodies. They require
    # one of Twilio's predefined template names, so keep the RAKSHA alert
    # content for the dashboard/log while sending the permitted template.
    provider_body = twilio["trial_template"] if twilio["trial_mode"] else body

    try:
        client = TwilioClient(twilio["account_sid"], twilio["auth_token"])
        message = client.messages.create(
            body=provider_body,
            from_=twilio["from_number"],
            to=recipient,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Twilio SMS failed: {exc}") from exc

    entry = {
        "ward_id": request.ward_id,
        "channel": "sms",
        "status": "sent",
        "recipient_role": request.recipient_role,
        "recipient_label": role["label"],
        "message_sid": message.sid,
        "message_status": getattr(message, "status", "queued"),
        "message": body,
        "provider_message_body": provider_body,
        "twilio_trial_mode": twilio["trial_mode"],
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "provider": "Twilio",
        "demo_only": False,
    }
    NOTIFICATION_LOG.append(entry)
    return entry


@app.get("/api/v1/demo/summary")
def demo_summary() -> dict[str, Any]:
    levels = {}
    for action in ACTIONS:
        levels[action["alert_level"]] = levels.get(action["alert_level"], 0) + 1
    return {
        "project": "SIH 26083",
        "system": "Extreme Heatwave Early Warning System",
        "mode": "offline_demo",
        "health_records": len(HEALTH),
        "wards": len(VULNERABILITY),
        "action_records": len(ACTIONS),
        "alert_levels": levels,
        "synthetic_health_notice": "Task 4 records are explicitly marked is_synthetic=true/source_type=synthetic_demo where supplied.",
    }
