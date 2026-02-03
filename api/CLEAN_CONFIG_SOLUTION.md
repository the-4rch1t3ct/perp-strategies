# Clean Config Solution - Remove Conflicts

## Current Status
✅ **Endpoint is working!** But nginx shows warnings about conflicting server names.

## Problem
Both `default` and `scalper-agent` configs have `server_name api.wagmi-global.eu`, causing nginx warnings.

## Solution Options

### Option 1: Remove server_name from default config (Keep Vantage2 location)
Since scalper-agent is handling the main API, we can remove the duplicate server block from default but keep the `/vantage2/` location by moving it to scalper-agent.

**But wait** - you want separation, so this isn't ideal.

### Option 2: Create Separate Vantage2 Config (Recommended)
Create a dedicated config file that ONLY handles `/vantage2/`:

1. **Remove `/vantage2/` location from default config**
2. **Create new file:** `/etc/nginx/sites-available/vantage2-api`
3. **Add only the Vantage2 server block**
4. **Enable it**

This keeps everything completely separate.

### Option 3: Keep Current Setup (Simplest)
The warnings are harmless - nginx is working fine. The endpoint works. We can just ignore the warnings.

## Recommended: Option 2

Since you want separation, let's create a dedicated vantage2-api config file.

### Steps:

1. **Remove `/vantage2/` location from default config:**
   ```bash
   sudo nano /etc/nginx/sites-available/default
   ```
   Delete lines 116-126 (the `/vantage2/` location block)

2. **Create new vantage2-api config:**
   ```bash
   sudo nano /etc/nginx/sites-available/vantage2-api
   ```

3. **Add this content:**
   ```nginx
   # Vantage2 API - Dedicated Configuration
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

4. **Enable it:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/vantage2-api /etc/nginx/sites-enabled/vantage2-api
   ```

5. **Disable default config** (since we moved the location block):
   ```bash
   sudo rm /etc/nginx/sites-enabled/default
   ```

6. **Test and reload:**
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

**Result:**
- `vantage2-api` config handles `/vantage2/*` → port 8003
- `scalper-agent` config handles everything else → port 8001/8000/8002
- No conflicts, completely separate configs
