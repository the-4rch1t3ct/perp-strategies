# Dashboard fresh start and 24h metrics

## One-time reset (fresh start)

After strategy or dashboard changes, you can reset all dashboard and historical performance data once:

```bash
bash /home/botadmin/perp-strategies/api/reset_dashboard_data.sh
```

This script:

- Removes `dashboard_24h_snapshots.json` (rolling 24h data)
- Removes legacy `hl_equity_snapshots.json`
- Clears `hyperliquid-trading-performance.json` and `hyperliquid-trading-positions.json` to `{}`

Then:

1. Restart the API: `bash /home/botadmin/perp-strategies/api/start_api.sh`
2. Optionally restart the traders so they repopulate performance from the exchange
3. Open the dashboard; 24h metrics will show "— (24h)" until enough snapshots exist, then show real deltas

## After reset: persistent behaviour

- **Rolling 24h:** Every time the dashboard (or `/portfolio`) is requested, the API appends a snapshot of equity, win_rate_pct, sharpe_ratio, and profit_factor to `dashboard_24h_snapshots.json` (up to 48 entries, last 48h).
- **24h comparison:** For each metric, the API returns the value closest to “24 hours ago” from those snapshots. If there is no snapshot that old yet, it uses the oldest snapshot so you still see a change.
- **Restarts:** The snapshot file is on disk under `/home/botadmin/clawd/memory/`. API and trader restarts do not clear it; only running `reset_dashboard_data.sh` does.

So: run the reset script once for a fresh start; after that, all 24h metrics are rolling and persistent across restarts.
