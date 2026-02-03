# Nginx 502 Bad Gateway - Debug Steps

## Current Status
- ✅ API is running on port 8003
- ✅ API responds to direct requests: `curl http://127.0.0.1:8003/vantage2/fundingOI`
- ✅ Location block is in correct server block (api.wagmi-global.eu, port 443)
- ❌ Public endpoint returns 502 Bad Gateway

## Debug Steps (Run these as root/sudo)

### 1. Check Nginx Error Logs
```bash
sudo tail -50 /var/log/nginx/error.log
```
Look for connection refused, timeouts, or permission errors.

### 2. Test from Nginx User
```bash
sudo -u www-data curl -v http://127.0.0.1:8003/vantage2/fundingOI
```
This simulates what nginx worker processes see.

### 3. Verify Nginx Configuration
```bash
sudo nginx -t
sudo nginx -T | grep -A 20 "location /vantage2"
```

### 4. Check if Port is Accessible
```bash
sudo netstat -tlnp | grep 8003
# Should show: tcp 0.0.0.0:8003 (listening on all interfaces)
```

### 5. Test Proxy Configuration Manually
```bash
# Test if nginx can reach the backend
sudo -u www-data nc -zv 127.0.0.1 8003
```

### 6. Check for SELinux (if applicable)
```bash
getenforce
# If Enforcing, might need to allow nginx to connect
```

## Potential Fixes

### Fix 1: Ensure Consistent Indentation
The location block uses spaces, rest uses tabs. Make it consistent:
```nginx
	location /vantage2/ {
		proxy_pass http://127.0.0.1:8003;
		proxy_http_version 1.1;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
		proxy_read_timeout 60s;
		add_header 'Access-Control-Allow-Origin' '*' always;
	}
```

### Fix 2: Add Proxy Connect Timeout
```nginx
location /vantage2/ {
	proxy_pass http://127.0.0.1:8003;
	proxy_connect_timeout 10s;
	proxy_send_timeout 60s;
	proxy_read_timeout 60s;
	proxy_http_version 1.1;
	proxy_set_header Host $host;
	proxy_set_header X-Real-IP $remote_addr;
	proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
	proxy_set_header X-Forwarded-Proto $scheme;
	add_header 'Access-Control-Allow-Origin' '*' always;
}
```

### Fix 3: Verify API Host Binding
Ensure the API is bound to 0.0.0.0 (all interfaces), not just 127.0.0.1.
Check `vantagev2_api.py` line 189:
```python
uvicorn.run(app, host="0.0.0.0", port=8003)  # ✅ Correct
```

## Most Likely Issue
The nginx error log will tell us exactly what's wrong. Run:
```bash
sudo tail -f /var/log/nginx/error.log
```
Then in another terminal:
```bash
curl https://api.wagmi-global.eu/vantage2/fundingOI
```
Watch the error log for the specific error message.
