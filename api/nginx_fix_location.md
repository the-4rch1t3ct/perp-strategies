# Fix: Move /vantage2/ location to correct server block

## Problem
The `/vantage2/` location block was added to the wrong server block (default server with `server_name _;`). It needs to be in the `api.wagmi-global.eu` server block.

## Solution

**File**: `/etc/nginx/sites-available/default`

**Find** (around line 127-134):
```nginx
    server_name api.wagmi-global.eu; # managed by Certbot


	location / {
		# First attempt to serve request as file, then
		# as directory, then fall back to displaying a 404.
		try_files $uri $uri/ =404;
	}
```

**Replace with**:
```nginx
    server_name api.wagmi-global.eu; # managed by Certbot

	# Increase timeouts for data fetching
	proxy_connect_timeout 60s;
	proxy_send_timeout 60s;
	proxy_read_timeout 60s;
	client_max_body_size 10M;

	# Vantage2 API endpoints (port 8003)
	location /vantage2/ {
		proxy_pass http://127.0.0.1:8003;
		proxy_http_version 1.1;
		
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
		
		proxy_read_timeout 60s;
		
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

	location / {
		# First attempt to serve request as file, then
		# as directory, then fall back to displaying a 404.
		try_files $uri $uri/ =404;
	}
```

## Also Remove

**Remove** the duplicate `/vantage2/` block from the default server block (around line 49-58):
```nginx
   # Vantage2 API endpoints (port 8003)
   location /vantage2/ {
       ...
   }
```

## Steps

1. Edit: `sudo nano /etc/nginx/sites-available/default`
2. Find line ~127 (`server_name api.wagmi-global.eu`)
3. Add the `/vantage2/` location block BEFORE `location /` (around line 130)
4. Remove the duplicate `/vantage2/` block from the default server (around line 49)
5. Test: `sudo nginx -t`
6. Reload: `sudo systemctl reload nginx`
7. Test: `curl https://api.wagmi-global.eu/vantage2/fundingOI`
