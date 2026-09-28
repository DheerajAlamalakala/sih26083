# SIH 26083 — Integrated Demo (Task 6)

This package integrates the supplied corrected Tasks 1–5 with a new Task 6 presentation/integration layer.

## Architecture

Task 1 weather → Task 2 thermal stress → Task 4 health risk
and Task 3 vulnerability → Task 4 / Task 6 GIS → Task 5 actions → Task 6 dashboard/notifications.

Task 6 consumes the supplied Task 4 health-risk output and Task 3 vulnerability/ward artifacts. It uses the existing Task 5 action engine for WardActionRecord generation and does not recalculate scientific health risk.

## Datasets

All source datasets from Tasks 1–5 are preserved exactly as supplied. The files under `task6/demo_data/` are byte-for-byte copies used as read-only demo inputs; the Task 6 code performs runtime field/geometry adaptation only.

Task 4 health records remain explicitly synthetic where the supplied data says `is_synthetic=true` and `source_type=synthetic_demo`.

## Run backend

```bash
cd task6/backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

## Run dashboard

In a second terminal:

```bash
cd task6/frontend
npm install
npm run dev
```

Open the Vite URL shown by the terminal. The frontend uses the FastAPI backend at `http://127.0.0.1:8000/api/v1` by default.

## Demo flow

1. Start FastAPI.
2. Start the React dashboard.
3. Show the ward map and alert distribution.
4. Click a ward to show Day 1–5 health-risk records and vulnerability.
5. Show municipal actions from the Task 5 action engine.
6. Trigger the simulated SMS/WhatsApp action.
7. Show `/docs` if an API view is useful for the demo.

No real Twilio credentials are required for demo mode.
