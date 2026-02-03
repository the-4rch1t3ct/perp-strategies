#!/bin/bash
# Start Vantage2 API (portfolio dashboard, fundingOI, etc.)
# Always stops any existing instance on the port before starting.

cd /home/botadmin/memecoin-perp-strategies/api

# Use venv if available
if [ -d "/home/botadmin/memecoin-perp-strategies/venv" ]; then
    source /home/botadmin/memecoin-perp-strategies/venv/bin/activate
fi

# Load env for live dashboard data (positions + equity + HL win rate from exchanges)
# Set HL_ACCOUNT_ADDRESS for Hyperliquid; ASTER_API_KEY + ASTER_API_SECRET for Aster
if [ -f "/home/botadmin/memecoin-perp-strategies/api/.env" ]; then
    set -a; source "/home/botadmin/memecoin-perp-strategies/api/.env"; set +a
fi
if [ -f "/home/botadmin/clawd/.env.portfolio" ]; then
    set -a; source "/home/botadmin/clawd/.env.portfolio"; set +a
fi

PORT=${PORT:-8003}

# Stop any existing process listening on PORT (no other dashboard instance)
stop_old() {
    local pids
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -t -i ":$PORT" 2>/dev/null)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser "$PORT/tcp" 2>/dev/null)
    else
        pids=""
    fi
    if [ -n "$pids" ]; then
        echo "Stopping existing process(es) on port $PORT: $pids"
        for pid in $pids; do
            kill "$pid" 2>/dev/null
        done
        sleep 2
        # Force kill if still running
        if command -v lsof >/dev/null 2>&1; then
            pids=$(lsof -t -i ":$PORT" 2>/dev/null)
        else
            pids=""
        fi
        if [ -n "$pids" ]; then
            for pid in $pids; do
                kill -9 "$pid" 2>/dev/null
            done
            sleep 1
        fi
        echo "Old instance stopped."
    fi
}

stop_old

echo "Starting Vantage2 API on port $PORT..."
echo "Dashboard: http://localhost:$PORT/portfolio-dashboard"
echo ""

exec python3 vantagev2_api.py
