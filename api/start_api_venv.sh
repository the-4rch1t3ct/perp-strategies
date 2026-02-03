#!/bin/bash
# Start the Live Indicators API with virtual environment

cd "$(dirname "$0")/.."

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q fastapi uvicorn[standard] httpx pandas numpy pydantic ccxt
fi

# Find available port
PORT=8001
while lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; do
    PORT=$((PORT + 1))
done

echo "=========================================="
echo "Memecoin Indicators API"
echo "=========================================="
echo "Port: $PORT"
echo "Endpoint: http://localhost:$PORT/indicators"
echo ""
echo "Endpoints:"
echo "  GET /indicators          - All 31 symbols"
echo "  GET /indicators/{symbol} - Single symbol"
echo "  GET /symbols            - Symbol list"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

cd api
export PORT=$PORT
python3 live_indicators_api_optimized.py
