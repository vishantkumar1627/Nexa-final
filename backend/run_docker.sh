#!/bin/bash
set -e

echo "=================================================================="
echo "      NEXUS AI ARCHITECTURE GENERATION SYSTEM - DOCKER LAUNCH"
echo "=================================================================="

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo "[-] Docker or Docker Compose is not installed. Please install Docker!"
    exit 1
fi

# Ensure .env exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[+] Created .env configuration from example template."
fi

# Start the Docker Stack
echo "[*] Launching multi-container stack via Docker Compose..."
if command -v docker-compose &> /dev/null; then
    docker-compose up --build -d
else
    docker compose up --build -d
fi

echo "=================================================================="
echo "[+] Stack successfully launched!"
echo "=================================================================="
echo "  - Nginx Reverse Proxy Gateway : http://localhost"
echo "  - FastAPI OpenAPI Documentation: http://localhost/docs"
echo "  - FastAPI Direct Swagger API  : http://localhost:8000/docs"
echo "  - WebSocket Progress Service  : http://localhost:8001/health"
echo "=================================================================="
echo "[*] To watch logs, run: docker-compose logs -f"
echo "[*] To run the system integration test pipeline, run:"
echo "    python scripts/demo_pipeline.py"
echo "=================================================================="
