# Setup Instructions: https://api.wagmi-global.eu/indicators

## Current Status

✅ API is running on `localhost:8002`  
⏳ Need to add nginx configuration to expose it at `https://api.wagmi-global.eu/indicators`

## Quick Setup (3 steps)

### 1. Ensure API is Running

The API should already be running. Verify:

```bash
curl http://localhost:8002/indicators
```

If not running, start it:

```bash
cd /home/botadmin/memecoin-perp-strategies
source venv/bin/activate
cd api
PORT=8002 nohup python3 live_indicators_api_optimized.py > /tmp/api_running.log 2>&1 &
```

### 2. Add Nginx Configuration

Edit the nginx config:

```bash
sudo nano /etc/nginx/sites-available/scalper-agent
```

Add the indicators endpoints **after** the `/health` location block and **before** the catch-all `location /` block. The content to add is in:

```
/home/botadmin/memecoin-perp-strategies/api/nginx_indicators_patch.txt
```

Or copy these location blocks:

```nginx
    # Indicators API endpoints (port 8002)
    location /indicators {
        proxy_pass http://127.0.0.1:8002/indicators;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_http_version 1.1;
        
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
        proxy_max_temp_file_size 0;
        proxy_buffering off;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
    }
    
    location ~ ^/indicators/(.+)$ {
        proxy_pass http://127.0.0.1:8002/indicators/$1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_http_version 1.1;
        proxy_buffering off;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }
    
    location /symbols {
        proxy_pass http://127.0.0.1:8002/symbols;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_http_version 1.1;
        proxy_buffering off;
        add_header 'Access-Control-Allow-Origin' '*' always;
    }
```

### 3. Test and Reload Nginx

```bash
# Test configuration
sudo nginx -t

# If test passes, reload nginx
sudo systemctl reload nginx
```

## Verify Deployment

```bash
# Test the endpoint
curl https://api.wagmi-global.eu/indicators

# Test single symbol
curl https://api.wagmi-global.eu/indicators/DOGE/USDT:USDT

# Test symbols list
curl https://api.wagmi-global.eu/symbols
```

## Available Endpoints

Once configured, these endpoints will be available:

- `https://api.wagmi-global.eu/indicators` - All 31 symbols with indicators
- `https://api.wagmi-global.eu/indicators/{symbol}` - Single symbol (e.g., `/indicators/DOGE/USDT:USDT`)
- `https://api.wagmi-global.eu/symbols` - List of all 31 allowed symbols

## Troubleshooting

1. **502 Bad Gateway**: API might not be running on port 8002
   ```bash
   ps aux | grep live_indicators_api_optimized
   ```

2. **404 Not Found**: Check nginx config is correct and reloaded
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

3. **Check nginx logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

4. **Check API logs**:
   ```bash
   tail -f /tmp/api_running.log
   ```

## Example Response

```json
{
  "success": true,
  "data": [
    {
      "symbol": "DOGE/USDT:USDT",
      "timestamp": "2026-01-26T23:15:00",
      "price": 0.12737,
      "volume": 27486387.0,
      "indicators": {
        "ema_fast": 0.12682,
        "ema_slow": 0.12661,
        "rsi": 73.56,
        "momentum": 0.0078,
        ...
      },
      "signal_strength": null,
      "entry_signal": null,
      "leverage": null
    }
    ... (30 more symbols)
  ],
  "timestamp": "2026-01-26T23:15:20",
  "latency_ms": 318.2
}
```

---

**After completing these steps, your API will be live at `https://api.wagmi-global.eu/indicators`!**
