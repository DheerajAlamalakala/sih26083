@echo off
cd /d "%~dp0task6\backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
