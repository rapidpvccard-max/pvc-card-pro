@echo off
title Rapid PVC Card Pro - Live Server
echo =========================================================
echo   Starting Rapid PVC Card Pro with Live Public Link...
echo =========================================================

REM Run the python tunnel manager
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe run_live_tunnel.py
) else (
    python run_live_tunnel.py
)

pause
