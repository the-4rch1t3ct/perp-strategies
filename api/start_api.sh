#!/bin/bash
# Startup script for Liquidation Heatmap API
# Ensures the API server is running on port 8004

cd /home/botadmin/perp-strategies/api

# Kill any existing instances and free port
pkill -f "uvicorn.*liquidation_heatmap_api.*8004" 2>/dev/null
fuser -k 8004/tcp 2>/dev/null
sleep 3

# Use venv Python if available (has fastapi); else system python3
PYTHON_BIN="/home/botadmin/perp-strategies/venv/bin/python"
[ ! -x "$PYTHON_BIN" ] && PYTHON_BIN="/usr/bin/python3"
# Start the API server (daemonize: nohup + disown so it survives shell exit)
nohup "$PYTHON_BIN" -m uvicorn liquidation_heatmap_api:app --host 0.0.0.0 --port 8004 >> /tmp/liquidation_api.log 2>&1 &
API_PID=$!
disown $API_PID 2>/dev/null || true
echo $API_PID > /tmp/liquidation_api.pid 2>/dev/null || true

sleep 6

# Verify it's running
if curl -s http://localhost:8004/api/trade/batch/hyperliquid?min_strength=0.70&max_distance=3.0&batch_id=0 > /dev/null 2>&1; then
    echo "✅ API server started successfully on port 8004"
    echo "   Local: http://localhost:8004/api/trade/batch/hyperliquid"
    echo "   Public: https://api.wagmi-global.eu/api/trade/batch/hyperliquid"
else
    echo "⚠️  API server may not have started correctly. Check /tmp/liquidation_api.log"
fi
