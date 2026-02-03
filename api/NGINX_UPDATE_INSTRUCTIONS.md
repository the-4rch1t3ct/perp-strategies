# Nginx Configuration Update for /vantage2/ Endpoint

## Issue
The `/vantage2/fundingOI` endpoint is not accessible via `https://api.wagmi-global.eu/vantage2/fundingOI` because nginx hasn't been configured to proxy it yet.

## Solution

The nginx configuration file has been updated: `nginx_wagmi_indicators.conf`

### Steps to Apply:

1. **Copy the updated config to nginx** (adjust path as needed):
   ```bash
   sudo cp /home/botadmin/memecoin-perp-strategies/api/nginx_wagmi_indicators.conf /etc/nginx/sites-available/api.wagmi-global.eu
   # Or if using conf.d:
   # sudo cp /home/botadmin/memecoin-perp-strategies/api/nginx_wagmi_indicators.conf /etc/nginx/conf.d/api.wagmi-global.eu.conf
   ```

2. **Test nginx configuration**:
   ```bash
   sudo nginx -t
   ```

3. **Reload nginx**:
   ```bash
   sudo systemctl reload nginx
   # Or:
   # sudo service nginx reload
   ```

4. **Verify the endpoint works**:
   ```bash
   curl https://api.wagmi-global.eu/vantage2/fundingOI
   ```

## What Was Added

The following location block was added to handle `/vantage2/` requests:

```nginx
location /vantage2/ {
    proxy_pass http://127.0.0.1:8003;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 60s;
    # CORS headers...
}
```

This proxies all `/vantage2/*` requests to the Vantage2 API running on port 8003.

## Important Notes

- The API must be running on port 8003 for this to work
- The location block is placed **before** the catch-all `location /` block so it takes precedence
- Timeout is set to 60s to allow for OI/Funding data fetching (~10 seconds)
