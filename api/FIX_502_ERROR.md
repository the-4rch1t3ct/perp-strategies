# Fixed: 502 Bad Gateway Error

## Problem
The API process had stopped running, causing nginx to return 502 Bad Gateway errors.

## Solution
Restarted the API process on port 8002.

## Current Status
✅ API is running and responding
✅ Nginx can connect to backend
✅ Endpoint working: `https://api.wagmi-global.eu/indicators`

## To Keep API Running

### Option 1: Systemd Service (Recommended)
Create a systemd service for automatic startup and restart:

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

### Option 2: Keep Process Running
Use `nohup` or `screen`/`tmux` to keep it running:

```bash
cd /home/botadmin/memecoin-perp-strategies
source venv/bin/activate
cd api
nohup python3 live_indicators_api_optimized.py > /tmp/api_running.log 2>&1 &
```

## Monitoring

Check if API is running:
```bash
ps aux | grep live_indicators_api_optimized | grep -v grep
```

Check API logs:
```bash
tail -f /tmp/api_running.log
```

Test endpoint:
```bash
curl https://api.wagmi-global.eu/indicators
```

---

**API is now running and accessible!**
