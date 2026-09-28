
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "offline_demo"

def test_forecast():
    response = client.get("/api/v1/forecast")
    assert response.status_code == 200
    assert response.json()["records"]

def test_wards_geojson():
    response = client.get("/api/v1/wards")
    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"

def test_alerts():
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert response.json()

def test_notification_is_simulated():
    ward = client.get("/api/v1/alerts").json()[0]["ward_id"]
    response = client.post("/api/v1/notifications/send", json={"ward_id": ward, "channel": "simulated"})
    assert response.status_code == 200
    assert response.json()["status"] == "simulated"


def test_trial_sms_uses_twilio_template(monkeypatch):
    from app import main

    class FakeMessage:
        sid = "SM_TEST_TRIAL_TEMPLATE"
        status = "queued"

    class FakeMessages:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return FakeMessage()

    class FakeClient:
        last_messages = None

        def __init__(self, account_sid, auth_token):
            self.messages = FakeMessages()
            FakeClient.last_messages = self.messages

    monkeypatch.setattr(main, "TwilioClient", FakeClient)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_TEST")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "TOKEN_TEST")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+10000000000")
    monkeypatch.setenv("RAKSHA_MUNICIPAL_WARD_OFFICER_PHONE", "+10000000001")
    monkeypatch.setenv("RAKSHA_TWILIO_TRIAL_MODE", "true")
    monkeypatch.setenv("RAKSHA_TWILIO_TRIAL_TEMPLATE", "sms_internal_alerts")

    ward = client.get("/api/v1/alerts").json()[0]["ward_id"]
    response = client.post("/api/v1/notifications/send", json={
        "ward_id": ward,
        "channel": "sms",
        "recipient_role": "municipal_ward_officer",
    })

    assert response.status_code == 200
    assert response.json()["twilio_trial_mode"] is True
    assert response.json()["provider_message_body"] == "sms_internal_alerts"
    assert FakeClient.last_messages.kwargs["body"] == "sms_internal_alerts"
