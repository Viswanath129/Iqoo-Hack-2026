@echo off
title JEVON Localhost Control Dashboard
color 0A

echo ======================================================================
echo           JEVON: ON-DEVICE DEVELOPER DECISION ENGINE
echo              Localhost Web Dashboard Launcher
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo Starting Localhost Web Dashboard on http://localhost:8000...
"%PYTHON_EXE%" run_dashboard.py --port 8000

pause
