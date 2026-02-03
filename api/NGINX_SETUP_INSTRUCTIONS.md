# Nginx Setup for Liquidation Heatmap

## Quick Setup

Run this command to automatically add the nginx configuration:

```bash
sudo bash /home/botadmin/memecoin-perp-strategies/api/add_liquidation_heatmap_nginx.sh
```

Then test and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Manual Setup

If you prefer to do it manually:

1. **Edit nginx config**:
   ```bash
   sudo nano /etc/nginx/sites-available/scalper-agent
   ```

2. **Find line 142** (the `location /` block) and add the content from:
   ```
   /home/botadmin/memecoin-perp-strategies/api/nginx_liquidation_patch.txt
   ```
   
   Insert it **BEFORE** the `location /` block.

3. **Test and reload**:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

## Verify

After setup, test the endpoints:

```bash
# Test UI
curl https://api.wagmi-global.eu/liquidation-heatmap

# Test API
curl https://api.wagmi-global.eu/api/heatmap/BTCUSDT

# Test symbols
curl https://api.wagmi-global.eu/api/heatmap/symbols
```

## What Gets Added

The script adds 4 location blocks:
1. `/liquidation-heatmap` - Main UI endpoint
2. `/liquidation-heatmap/*` - UI sub-paths
3. `/api/heatmap` - API endpoint
4. `/api/heatmap/*` - API sub-paths (symbols, etc.)

All proxy to `http://127.0.0.1:8004` where the API is running.
