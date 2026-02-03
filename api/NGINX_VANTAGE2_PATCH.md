# Nginx Configuration Patch for /vantage2/ Endpoint

## Quick Fix

Add this location block to your nginx configuration for `api.wagmi-global.eu`:

**Add it BEFORE the catch-all `location /` block** (around line 88-89 in the config)

```nginx
    # Vantage2 API endpoints (port 8003)
    location /vantage2/ {
        proxy_pass http://127.0.0.1:8003;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeout for OI/Funding fetches
        proxy_read_timeout 60s;
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
        
        # Handle preflight
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }
```

## Steps

1. **Find your nginx config file**:
   ```bash
   # Common locations:
   /etc/nginx/sites-available/api.wagmi-global.eu
   /etc/nginx/sites-enabled/api.wagmi-global.eu
   /etc/nginx/conf.d/api.wagmi-global.eu.conf
   ```

2. **Edit the file** and add the location block above **before** the `location /` block

3. **Test the config**:
   ```bash
   sudo nginx -t
   ```

4. **Reload nginx**:
   ```bash
   sudo systemctl reload nginx
   ```

5. **Test the endpoint**:
   ```bash
   curl https://api.wagmi-global.eu/vantage2/fundingOI
   ```

## Verify API is Running

Make sure the Vantage2 API is running on port 8003:
```bash
ps aux | grep vantagev2_api
curl http://localhost:8003/vantage2/fundingOI
```

If not running, start it:
```bash
cd /home/botadmin/memecoin-perp-strategies/api
source ../venv/bin/activate
python3 vantagev2_api.py &
```
