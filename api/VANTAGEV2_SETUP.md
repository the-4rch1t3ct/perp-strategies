# Vantage2 API Setup

## Overview

Modular API endpoint at `/vantage2/fundingOI` that provides:
- Open Interest (OI) data
- Funding Rate data
- Minimal, compact JSON response

## Endpoint

**URL**: `https://api.wagmi-global.eu/vantage2/fundingOI`

**Response Format** (compact):
```json
{
  "ok": true,
  "d": [
    {
      "s": "DOGE/USDT:USDT",  // symbol
      "oi": 1234567.89,        // open_interest
      "fr": 0.0001             // funding_rate (8h)
    }
  ],
  "t": "2026-01-27T17:48:39.296285"
}
```

## Field Abbreviations

- `s` = symbol
- `oi` = open interest
- `fr` = funding rate (8-hour funding rate)

## Setup

### 1. Install Dependencies

```bash
cd /home/botadmin/memecoin-perp-strategies/api
pip install fastapi uvicorn ccxt pandas numpy httpx
```

### 2. Start API

```bash
# Option 1: Direct
python3 vantagev2_api.py

# Option 2: Using script
./start_vantagev2.sh

# Option 3: Background
nohup python3 vantagev2_api.py > vantagev2.log 2>&1 &
```

Default port: **8003**

### 3. Configure Nginx

Add to nginx config (see `nginx_vantagev2_patch.txt`):

```nginx
location /vantagev2 {
    proxy_pass http://127.0.0.1:8003;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
}
```

Then reload nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Systemd Service (Optional)

Create `/etc/systemd/system/vantagev2-api.service`:

```ini
[Unit]
Description=VantageV2 API
After=network.target

[Service]
Type=simple
User=botadmin
WorkingDirectory=/home/botadmin/memecoin-perp-strategies/api
ExecStart=/home/botadmin/memecoin-perp-strategies/venv/bin/python3 vantagev2_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable vantagev2-api
sudo systemctl start vantagev2-api
```

## Testing

```bash
# Test locally
curl http://localhost:8003/vantagev2

# Test via nginx
curl https://api.wagmi-global.eu/vantage2/fundingOI
```

## Data Sources

- **Open Interest**: Binance Futures API
- **Funding Rate**: Binance Futures API (8-hour funding)

## Performance

- **Cache**: OI/Funding cached for 15 seconds
- **Refresh Rate**: Every 15 seconds (4x per minute)
- **Rate Limiting**: 20 requests/second (248 req/min total, well within Binance's 1200 req/min limit)
- **Expected Latency**: < 1 second for cached data, ~3 seconds for fresh fetch
- **Data Freshness**: Maximum freshness while staying within safe rate limits

## Differences from /indicators

1. **Compact format**: Short field names (s, oi, fr)
2. **OI & Funding only**: No strategy signals, just OI and funding data
3. **Minimal payload**: Only 3 fields per symbol
4. **Modular structure**: `/vantage2/` prefix allows adding more endpoints (e.g., `/vantage2/otherData`)
