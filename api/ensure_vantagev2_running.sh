#!/bin/bash
# Ensure vantagev2 API is running on port 8003
# Run this via cron every 5 minutes: */5 * * * * /home/botadmin/memecoin-perp-strategies/api/ensure_vantagev2_running.sh

PORT=8003
SCRIPT_DIR="/home/botadmin/memecoin-perp-strategies/api"
LOG_FILE="/tmp/vantagev2_api.log"

cd "$SCRIPT_DIR"

# Check if port is in use
if ! lsof -i :$PORT >/dev/null 2>&1; then
    echo "$(date): Port $PORT not in use, starting vantagev2 API..." >> "$LOG_FILE"
    source ../venv/bin/activate
    nohup python3 vantagev2_api.py >> "$LOG_FILE" 2>&1 &
    sleep 3
    if lsof -i :$PORT >/dev/null 2>&1; then
        echo "$(date): ✅ Vantage2 API started successfully" >> "$LOG_FILE"
    else
        echo "$(date): ❌ Failed to start Vantage2 API" >> "$LOG_FILE"
    fi
fi
