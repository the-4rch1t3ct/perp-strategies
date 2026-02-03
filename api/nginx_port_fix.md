# Fix: Nginx Connecting to Wrong Port (8001 instead of 8003)

## Problem
Error logs show nginx is trying to connect to port **8001**:
```
upstream: "http://127.0.0.1:8001/vantage2/fundingOI"
```

But the API is running on port **8003**.

## Root Cause
The nginx config file shows port 8003, but nginx might not have reloaded, OR there's a location block matching issue due to indentation (spaces vs tabs).

## Solution

### Step 1: Verify Current Config
The location block at line 117-126 should have port 8003, but check it's using tabs (not spaces) for indentation.

### Step 2: Fix the Location Block
Replace lines 116-126 with this (using tabs, not spaces):

```nginx
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
		proxy_set_header Connection "";
		
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
```

**Important**: Use tabs (not spaces) for indentation to match the rest of the file!

### Step 3: Test and Reload
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 4: Verify
```bash
curl https://api.wagmi-global.eu/vantage2/fundingOI
```

If still getting 502, check error logs again:
```bash
sudo tail -f /var/log/nginx/error.log
```

## Alternative: Check if Another Config is Matching
There's a file `/etc/nginx/sites-available/scalper-agent` with port 8001. Check if it's enabled:
```bash
ls -la /etc/nginx/sites-enabled/
```

If `scalper-agent` is symlinked there and has a matching server_name, it might be catching the request first.
