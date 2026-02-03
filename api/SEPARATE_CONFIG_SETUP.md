# Separate Config Setup for Vantage2 API

## Current Situation
- Only `scalper-agent` config is enabled
- Both `default` and `scalper-agent` have `server_name api.wagmi-global.eu`
- The `default` config has the `/vantage2/` location block but isn't enabled
- Scalper-agent's catch-all `location /` is catching everything

## Solution: Enable Default Config

Nginx processes server blocks in the order configs are loaded. When multiple server blocks match the same `server_name`, nginx uses the first one that matches the request path.

### Option 1: Enable Both Configs (Recommended)

1. **Enable the default config:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
   ```

2. **Verify both are enabled:**
   ```bash
   ls -la /etc/nginx/sites-enabled/
   ```
   Should show both `default` and `scalper-agent`

3. **Test configuration:**
   ```bash
   sudo nginx -t
   ```

4. **Reload nginx:**
   ```bash
   sudo systemctl reload nginx
   ```

**How it works:**
- Nginx loads configs alphabetically: `default` comes before `scalper-agent`
- When a request comes for `/vantage2/fundingOI`:
  - Nginx checks the `default` config's server block first
  - Finds `location /vantage2/` → matches! → proxies to port 8003 ✅
- When a request comes for `/analyze/signals`:
  - Nginx checks `default` config → no match
  - Checks `scalper-agent` config → finds `location /analyze/signals` → matches! ✅
- When a request comes for `/` (root):
  - Nginx checks `default` config → finds `location /` → matches (but returns 404)
  - OR scalper-agent's catch-all handles it

### Option 2: Create Separate Config File (Even Cleaner)

Create a dedicated config file just for Vantage2:

1. **Create new config:**
   ```bash
   sudo nano /etc/nginx/sites-available/vantage2-api
   ```

2. **Add this content:**
   ```nginx
   # Vantage2 API - Separate Configuration
   server {
       listen 443 ssl http2;
       server_name api.wagmi-global.eu;

       ssl_certificate /etc/letsencrypt/live/api.wagmi-global.eu/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/api.wagmi-global.eu/privkey.pem;
       include /etc/letsencrypt/options-ssl-nginx.conf;
       ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

       # Vantage2 API endpoints (port 8003)
       location /vantage2/ {
           proxy_pass http://127.0.0.1:8003;
           proxy_http_version 1.1;
           
           proxy_connect_timeout 10s;
           proxy_send_timeout 60s;
           proxy_read_timeout 60s;
           
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           
           proxy_buffering off;
           
           add_header 'Access-Control-Allow-Origin' '*' always;
           add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
           add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
           
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
   }
   ```

3. **Enable it:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/vantage2-api /etc/nginx/sites-enabled/vantage2-api
   ```

4. **Remove `/vantage2/` from default config** (to avoid conflicts)

5. **Test and reload:**
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

**How it works:**
- `vantage2-api` config handles `/vantage2/*` requests
- `scalper-agent` config handles everything else
- Both are completely separate files

## Recommendation

**Use Option 1** (enable default config) - it's simpler and the `/vantage2/` location is already there. The configs will work together because nginx matches the most specific location first.
