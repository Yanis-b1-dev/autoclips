@echo off
echo ==============================
echo     AUTOCLIPS LAUNCHER
echo ==============================
echo.

REM Check Python
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo Please install Python from https://python.org
    pause
    exit /b
)

REM Check ffmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] ffmpeg is not installed or not on PATH.
    echo Please install ffmpeg:
    echo   1. Download from https://ffmpeg.org/download.html
    echo   2. Extract and add the bin/ folder to your PATH
    echo   Or install via winget: winget install ffmpeg
    pause
    exit /b
)

echo [OK] Python found
echo [OK] ffmpeg found
echo.

REM Install dependencies
echo Installing Python dependencies...
py -m pip install -r requirements.txt -q
echo [OK] Dependencies installed
echo.

REM Create required folders
if not exist uploads mkdir uploads
if not exist downloads mkdir downloads
if not exist output mkdir output

REM Start Flask and open browser
echo Starting Autoclips server at http://localhost:5000
start "" http://localhost:5000
py app.py
pause
