#!/usr/bin/env bash
# One-time reset of dashboard and historical performance data for a fresh start.
# Run this once, then restart the API (and optionally the traders). After that, all data is persistent across restarts.
#
# Usage: bash /home/botadmin/perp-strategies/api/reset_dashboard_data.sh

set -e
MEMORY="/home/botadmin/clawd/memory"

echo "=== Dashboard fresh start: resetting all dashboard and HL performance data ==="

# Rolling 24h snapshots (dashboard) – remove so 24h metrics start fresh
if [ -f "$MEMORY/dashboard_24h_snapshots.json" ]; then
  rm -f "$MEMORY/dashboard_24h_snapshots.json"
  echo "  Removed dashboard_24h_snapshots.json"
fi

# Legacy equity-only snapshots (no longer used)
if [ -f "$MEMORY/hl_equity_snapshots.json" ]; then
  rm -f "$MEMORY/hl_equity_snapshots.json"
  echo "  Removed hl_equity_snapshots.json"
fi

# Hyperliquid performance and positions – clear so trader/dashboard repopulate from live
echo '{}' > "$MEMORY/hyperliquid-trading-performance.json"
echo '{}' > "$MEMORY/hyperliquid-trading-positions.json"
echo "  Cleared hyperliquid-trading-performance.json and hyperliquid-trading-positions.json"

# From now on, dashboard only shows trades that closed on or after this time (chart, overview, win rate, etc.)
printf '%s\n' "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\"}" > "$MEMORY/dashboard_performance_since.json"
echo "  Set dashboard_performance_since.json to $(date -u +%Y-%m-%dT%H:%M:%SZ) (only post-reset trades will show)"

echo ""
echo "Done. Next steps:"
echo "  1. Restart the API:  /home/botadmin/perp-strategies/api/start_api.sh"
echo "  2. Restart trader if desired:  pkill -f trader.py; /home/botadmin/clawd/start_hyperliquid_trader.sh"
echo "  3. Open the dashboard; 24h metrics will fill as new snapshots are stored (persistent from here on)."
