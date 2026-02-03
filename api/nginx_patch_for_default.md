# Nginx Config Patch for /etc/nginx/sites-available/default

## Location to Edit

Edit `/etc/nginx/sites-available/default` and find the server block for `api.wagmi-global.eu` (around line 115).

## What to Replace

**FIND THIS** (around line 115-122):
```nginx
    server_name api.wagmi-global.eu; # managed by Certbot


	location / {
		# First attempt to serve request as file, then
		# as directory, then fall back to displaying a 404.
		try_files $uri $uri/ =404;
	}
```

**REPLACE WITH THIS**:
```nginx
    server_name api.wagmi-global.eu; # managed by Certbot

	# Increase timeouts for data fetching
	proxy_connect_timeout 60s;
	proxy_send_timeout 60s;
	proxy_read_timeout 60s;
	client_max_body_size 10M;

	# Main indicators endpoint (port 8002)
	location /indicators {
		proxy_pass http://127.0.0.1:8002;
		proxy_http_version 1.1;
		
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
		
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

	# Single symbol indicator endpoint
	location ~ ^/indicators/(.+)$ {
		proxy_pass http://127.0.0.1:8002/indicators/$1;
		proxy_http_version 1.1;
		
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
		
		add_header 'Access-Control-Allow-Origin' '*' always;
	}

	# Symbols list endpoint
	location /symbols {
		proxy_pass http://127.0.0.1:8002/symbols;
		proxy_http_version 1.1;
		
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
		
		add_header 'Access-Control-Allow-Origin' '*' always;
	}

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

## Steps

1. **Edit the file**:
   ```bash
   sudo nano /etc/nginx/sites-available/default
   # or
   sudo vi /etc/nginx/sites-available/default
   ```

2. **Find the server block** for `api.wagmi-global.eu` (around line 115)

3. **Replace** the location block as shown above

4. **Test the config**:
   ```bash
   sudo nginx -t
   ```

5. **Reload nginx**:
   ```bash
   sudo systemctl reload nginx
   ```

6. **Test the endpoint**:
   ```bash
   curl https://api.wagmi-global.eu/vantage2/fundingOI
   ```

## Important Notes

- The `/vantage2/` location block must be placed **BEFORE** the catch-all `location /` block
- This ensures `/vantage2/*` requests are proxied to port 8003 before falling through to the default handler
- Make sure the Vantage2 API is running on port 8003
