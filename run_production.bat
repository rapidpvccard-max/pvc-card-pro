@echo off
echo =========================================
echo Starting PVC Card Pro in Production Mode
echo =========================================

REM Activate virtual environment
call venv\Scripts\activate

REM Set environment variable to enforce production behavior
set ENVIRONMENT=production

REM On Windows, Uvicorn can run with multiple workers directly
echo Starting Uvicorn with 4 workers...
uvicorn app:app --host 127.0.0.1 --port 8000 --workers 4

pause
