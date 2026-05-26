@echo off
echo ==================================================================
echo       NEXUS AI ARCHITECTURE GENERATION SYSTEM - LOCAL LAUNCH
echo ==================================================================
echo [*] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Python is not installed. Please install Python 3.10+!
    pause
    exit /b 1
)

echo [*] Copying environmental template if .env does not exist...
if not exist .env (
    copy .env.example .env
    echo [+] Created .env configuration from example template.
)

echo [*] Installing local dependencies from requirements.txt...
pip install -r requirements.txt

echo ==================================================================
echo [+] Launching local FastAPI Gateway (SQLite fallback database)...
echo   - Local Swagger Documentation: http://127.0.0.1:8000/docs
echo   - Local Health Check Status  : http://127.0.0.1:8000/health
echo ==================================================================
echo [*] Running server. Press Ctrl+C to terminate.
python -m uvicorn services.api_gateway.main:app --host 127.0.0.1 --port 8000 --reload
pause
