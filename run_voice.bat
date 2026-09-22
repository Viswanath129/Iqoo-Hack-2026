@echo off
title Viswa JAV - NPU Voice Computer Assistant
color 0B
cd /d "B:\projects\viswa_jav"

echo ======================================================================
echo          VISWA JAV - QUALCOMM SNAPDRAGON NPU VOICE ASSISTANT
echo ======================================================================
echo  Hardware : Snapdragon X Plus - Hexagon NPU (45 TOPS)
echo  Features : Hardware OCR + On-Device Speech Recognition + Speech Output
echo  Emergency: Move mouse cursor to TOP-LEFT corner to abort anytime
echo ======================================================================
echo.

:: Use the native ARM64 Python environment
set "PYTHON_EXE=C:\Users\kasiv\AppData\Local\Programs\Python\Python311-arm64\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

:VOICE_LOOP
echo [READY] Activating microphone for voice input...
echo.

"%PYTHON_EXE%" -m typesafe_computer_use.cli --voice --speak --act %*

echo.
echo ======================================================================
echo Task completed.
echo Press [S] to speak another goal, or [Q] to exit.
echo ======================================================================
choice /c SQ /n /m "Press [S] to speak another command, or [Q] to quit: "
if errorlevel 2 goto EXIT
if errorlevel 1 goto VOICE_LOOP

:EXIT
echo Exiting Viswa JAV Voice Assistant. Goodbye!
timeout /t 2 >nul
