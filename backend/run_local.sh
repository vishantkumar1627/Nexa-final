#!/bin/bash
set -e

echo "=================================================================="
echo "      NEXUS AI ARCHITECTURE GENERATION SYSTEM - LOCAL LAUNCH"
echo "=================================================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[-] Python3 is not installed. Please install Python 3.10+!"
    exit 1
fi

# Ensure .env exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[+] Created .env configuration from example template."
fi

# Install requirements
echo "[*] Installing dependencies..."
pip install -r requirements.txt

echo "=================================================================="
echo "[+] Launching local FastAPI Gateway (SQLite fallback database)..."
echo "  - Local Swagger Documentation: http://127.0.0.1:8000/docs"
echo "  - Local Health Check Status  : http://127.0.0.1:8000/health"
echo "=================================================================="
echo "[*] Running server. Press Ctrl+C to terminate."
python3 -m uvicorn services.api_gateway.main:app --host 127.0.0.1 --port 8000 --reload
