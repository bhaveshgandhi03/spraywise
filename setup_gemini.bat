@echo off
REM Quick Setup Script for Google Gemini Integration
REM Run this from project root: .\setup_gemini.bat

echo.
echo ========================================
echo KisanRakshak - Google Gemini Setup
echo ========================================
echo.

REM Check if .venv exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
) else (
    echo Virtual environment already exists.
)

REM Activate venv
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements-dev.txt

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Get API key from https://ai.google.dev/
echo 2. Copy .env.example to .env
echo 3. Edit .env and paste your API key
echo 4. Run: $env:GOOGLE_GEMINI_API_KEY = "your_key_here"
echo 5. Run: uvicorn app.main:app --reload
echo 6. Open http://127.0.0.1:8000 in your browser
echo.
echo.venv\Scripts\activate to activate the environment in future sessions.
echo.
pause
