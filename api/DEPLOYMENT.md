# Deployment Guide - api.wagmi-global.eu/indicators

## Overview

This guide explains how to deploy the Live Indicators API to `https://api.wagmi-global.eu/indicators`.

## Prerequisites

- Nginx installed and running
- Python 3 with virtual environment
- SSL certificate for api.wagmi-global.eu (Let's Encrypt recommended)

## Deployment Steps

### 1. Ensure API is Running

The API should be running on port 8002 (or your chosen port):

```bash
cd /home/botadmin/memecoin-perp-strategies
source venv/bin/activate
cd api
PORT=8002 nohup python3 live_indicators_api_optimized.py > /tmp/api_running.log 2>&1 &
```

### 2. Install Nginx Configuration

```bash
# Copy the nginx config
sudo cp /home/botadmin/memecoin-perp-strategies/api/nginx_wagmi_indicators.conf \
       /etc/nginx/sites-available/wagmi-indicators

# Enable the site
sudo ln -s /etc/nginx/sites-available/wagmi-indicators \
          /etc/nginx/sites-enabled/wagmi-indicators

# Test nginx configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 3. SSL Certificate (if not already configured)

```bash
# Install certbot if needed
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d api.wagmi-global.eu

# Auto-renewal is usually set up automatically
```

### 4. Update Nginx Config with SSL Paths

After obtaining SSL certificates, update `/etc/nginx/sites-available/wagmi-indicators` with the actual SSL certificate paths (certbot usually does this automatically).

### 5. Verify Deployment

```bash
# Test the endpoint
curl https://api.wagmi-global.eu/indicators

# Check API is running
curl http://localhost:8002/indicators

# Check nginx logs
sudo tail -f /var/log/nginx/wagmi_indicators_access.log
sudo tail -f /var/log/nginx/wagmi_indicators_error.log
```

## Endpoints

Once deployed, the following endpoints will be available:

- `https://api.wagmi-global.eu/indicators` - All 31 symbols
- `https://api.wagmi-global.eu/indicators/{symbol}` - Single symbol
- `https://api.wagmi-global.eu/symbols` - Symbol list
- `https://api.wagmi-global.eu/` - API info

## Systemd Service (Optional)

Create a systemd service for automatic startup:

```bash
sudo nano /etc/systemd/system/wagmi-indicators-api.service
```

Add:

```ini
[Unit]
Description=Wagmi Indicators API
After=network.target

[Service]
Type=simple
User=botadmin
WorkingDirectory=/home/botadmin/memecoin-perp-strategies/api
Environment="PORT=8002"
ExecStart=/home/botadmin/memecoin-perp-strategies/venv/bin/python3 live_indicators_api_optimized.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wagmi-indicators-api
sudo systemctl start wagmi-indicators-api
sudo systemctl status wagmi-indicators-api
```

## Monitoring

```bash
# Check API process
ps aux | grep live_indicators_api_optimized

# Check API logs
tail -f /tmp/api_running.log

# Check nginx status
sudo systemctl status nginx

# Check API response time
time curl -s https://api.wagmi-global.eu/indicators > /dev/null
```

## Troubleshooting

1. **API not responding**: Check if process is running and port is correct
2. **502 Bad Gateway**: API might not be running or wrong port in nginx config
3. **SSL errors**: Verify SSL certificate is valid and paths are correct
4. **CORS issues**: Check nginx CORS headers are set correctly

## Rollback

If needed, disable the site:

```bash
sudo rm /etc/nginx/sites-enabled/wagmi-indicators
sudo systemctl reload nginx
```
