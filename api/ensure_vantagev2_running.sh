#!/bin/bash
# Ensure vantagev2 API is running on port 8003
# Run this via cron every 5 minutes: */5 * * * * /home/botadmin/perp-strategies/api/ensure_vantagev2_running.sh

PORT=8003
SCRIPT_DIR="/home/botadmin/perp-strategies/api"
LOG_FILE="/tmp/vantagev2_api.log"

# Use same Python as start_vantagev2.sh (clawd .venv has FastAPI/uvicorn)
PYTHON_BIN="/home/botadmin/clawd/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

cd "$SCRIPT_DIR"

# Load env for HL_ACCOUNT_ADDRESS (optional, for live dashboard)
if [ -f "/home/botadmin/perp-strategies/api/.env" ]; then
    set -a; source "/home/botadmin/perp-strategies/api/.env"; set +a
fi
if [ -f "/home/botadmin/clawd/.env.portfolio" ]; then
    set -a; source "/home/botadmin/clawd/.env.portfolio"; set +a
fi

# Check if port is in use
if ! lsof -i :$PORT >/dev/null 2>&1; then
    echo "$(date): Port $PORT not in use, starting vantagev2 API..." >> "$LOG_FILE"
    nohup "$PYTHON_BIN" vantagev2_api.py >> "$LOG_FILE" 2>&1 &
    sleep 3
    if lsof -i :$PORT >/dev/null 2>&1; then
        echo "$(date): ✅ Vantage2 API started successfully" >> "$LOG_FILE"
    else
        echo "$(date): ❌ Failed to start Vantage2 API" >> "$LOG_FILE"
    fi
fi
