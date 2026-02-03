#!/bin/bash
# Start the Live Indicators API

cd "$(dirname "$0")"

# Check if port 8001 is available, if not try 8002, etc.
PORT=8001
while lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; do
    PORT=$((PORT + 1))
done

echo "Starting Memecoin Indicators API on port $PORT..."
echo "API will be available at: http://localhost:$PORT"
echo ""
echo "Endpoints:"
echo "  - GET http://localhost:$PORT/indicators (all 31 symbols)"
echo "  - GET http://localhost:$PORT/indicators/{symbol} (single symbol)"
echo "  - GET http://localhost:$PORT/symbols (symbol list)"
echo ""
echo "Press Ctrl+C to stop"
echo ""

export PORT=$PORT
python3 live_indicators_api_optimized.py
