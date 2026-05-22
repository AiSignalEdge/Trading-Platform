#!/bin/bash
# Trading Backend Startup Script
# Sets required env vars and starts uvicorn

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Database credentials
export DATABASE_URL="postgresql+asyncpg://trading_user:Trading%402025@localhost:5432/trading_db"

# Start uvicorn
exec ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8080