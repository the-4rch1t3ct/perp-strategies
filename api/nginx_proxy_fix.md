# Nginx Proxy Pass Fix

## Issue
502 Bad Gateway suggests nginx can't properly proxy to the backend.

## Current Configuration
```nginx
location /vantage2/ {
    proxy_pass http://127.0.0.1:8003;
    ...
}
```

## Problem
When you access `https://api.wagmi-global.eu/vantage2/fundingOI`, nginx passes `/vantage2/fundingOI` to `http://127.0.0.1:8003/vantage2/fundingOI`, which should work, but there might be an issue with how the path is being handled.

## Solution Options

### Option 1: Keep full path (current - should work)
The current config should work. If it doesn't, check:
- Nginx error logs: `sudo tail -f /var/log/nginx/error.log`
- Ensure API is listening on 0.0.0.0:8003 (it is)
- Check if nginx worker can connect: `sudo -u www-data curl http://127.0.0.1:8003/vantage2/fundingOI`

### Option 2: Strip the path prefix
If you want to strip `/vantage2` from the path before proxying:
```nginx
location /vantage2/ {
    proxy_pass http://127.0.0.1:8003/;  # Note trailing slash
    ...
}
```
This would pass `/fundingOI` instead of `/vantage2/fundingOI` - but this won't work since the API expects `/vantage2/fundingOI`.

### Option 3: Use rewrite (if needed)
```nginx
location /vantage2/ {
    rewrite ^/vantage2/(.*)$ /vantage2/$1 break;
    proxy_pass http://127.0.0.1:8003;
    ...
}
```

## Recommended: Check Error Logs First
```bash
sudo tail -f /var/log/nginx/error.log
```
Then try accessing the endpoint and see what error appears.

## Also Check
1. Ensure consistent indentation (tabs vs spaces)
2. Verify nginx reloaded: `sudo systemctl status nginx`
3. Test from nginx user perspective: `sudo -u www-data curl http://127.0.0.1:8003/vantage2/fundingOI`
