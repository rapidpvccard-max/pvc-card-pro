@echo off
title Rapid PVC Card Pro - Localhost Server
echo =========================================================
echo   Starting Rapid PVC Card Pro on Localhost...
echo =========================================================
echo.
echo   Localhost URL: http://localhost:8000
echo   Alternative:   http://127.0.0.1:8000
echo.
echo   Opening your default web browser...
echo   Press Ctrl + C anytime to stop the server.
echo =========================================================
echo.

REM Automatically open browser
start "" http://localhost:8000

REM Start Uvicorn FastAPI server with auto-reload
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
) else (
    python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
)

pause
