#!/bin/bash
# Startup script for Liquidation Heatmap API

cd "$(dirname "$0")"
cd ..

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies if needed
pip install -q websocket-client fastapi uvicorn httpx pydantic

# Start the API server
echo "Starting Liquidation Heatmap API..."
echo "Access UI at: http://localhost:8004"
echo "API docs at: http://localhost:8004/docs"
echo "Wagmi URL: https://api.wagmi-global.eu/liquidation-heatmap"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python api/liquidation_heatmap_api.py
