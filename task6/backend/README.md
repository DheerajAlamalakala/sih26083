# Task 6 Backend

FastAPI integration layer for SIH 26083.

Run from `task6/backend`:
```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API reads the existing Task 1/3/4/5 artifacts from `../demo_data` and uses the existing Task 5 action engine. It does not modify source datasets or recalculate scientific health risk.

Open `/docs` for the interactive API documentation.


### Real SMS / Twilio
Install dependencies with `python -m pip install -r requirements.txt`. Set the Twilio Account SID, Auth Token, and Twilio sender number in environment variables (or a local `.env` that your environment loads), plus phone numbers for the three stakeholder roles in `backend/.env.example`. The dashboard then sends real SMS through Twilio from the Stage 3 response controls. If Twilio is not configured, the UI reports that clearly rather than claiming a real SMS was sent. Twilio credentials should never be committed to source control.


### Twilio trial mode

Twilio trial SMS accounts require predefined message templates. This build therefore defaults `RAKSHA_TWILIO_TRIAL_MODE=true` and sends the `sms_internal_alerts` template while retaining the full RAKSHA alert/advisory in the dashboard and notification log. After upgrading Twilio, set `RAKSHA_TWILIO_TRIAL_MODE=false` to send the custom RAKSHA SMS body.
