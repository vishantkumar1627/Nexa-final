@echo off
echo ==================================================================
echo       NEXUS AI ARCHITECTURE GENERATION SYSTEM - DOCKER LAUNCH
echo ==================================================================
echo [*] Checking docker-compose status...
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Docker Compose is not installed or not running. Please install Docker Desktop!
    pause
    exit /b 1
)

echo [*] Copying environmental template if .env does not exist...
if not exist .env (
    copy .env.example .env
    echo [+] Created .env configuration from example template.
)

echo [*] Launching multi-container stack via Docker Compose...
docker-compose up --build -d

echo ==================================================================
echo [+] Stack successfully launched!
echo ==================================================================
echo   - Nginx Reverse Proxy Gateway : http://localhost
echo   - FastAPI OpenAPI Documentation: http://localhost/docs
echo   - FastAPI Direct Swagger API  : http://localhost:8000/docs
echo   - WebSocket Progress Service  : http://localhost:8001/health
echo ==================================================================
echo [*] To watch logs, run: docker-compose logs -f
echo [*] To run the system integration test pipeline, run:
echo     python scripts/demo_pipeline.py
echo ==================================================================
pause
