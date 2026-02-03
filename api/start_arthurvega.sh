#!/bin/bash
# Start ArthurVega API

cd /home/botadmin/memecoin-perp-strategies/api

# Use venv if available
if [ -d "/home/botadmin/memecoin-perp-strategies/venv" ]; then
    source /home/botadmin/memecoin-perp-strategies/venv/bin/activate
fi

PORT=${PORT:-8003}

echo "Starting ArthurVega API on port $PORT..."
echo "Endpoint: http://localhost:$PORT/arthurvega/fundingOI"
echo ""

python3 arthurvega_api.py
