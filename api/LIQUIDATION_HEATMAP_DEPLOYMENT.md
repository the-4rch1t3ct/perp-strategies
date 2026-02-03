# Liquidation Heatmap Deployment Guide

## ✅ Configuration Complete

The Liquidation Heatmap API is configured to:
- **Port**: 8004
- **Wagmi URL**: `https://api.wagmi-global.eu/liquidation-heatmap`

---

## 🚀 Quick Deployment

### Step 1: Start the API

```bash
cd /home/botadmin/memecoin-perp-strategies
python api/liquidation_heatmap_api.py
```

Or run in background:
```bash
nohup python api/liquidation_heatmap_api.py > /tmp/liquidation_heatmap.log 2>&1 &
```

### Step 2: Configure Nginx

**Option A: Use setup script (recommended)**
```bash
cd /home/botadmin/memecoin-perp-strategies
sudo ./api/setup_liquidation_heatmap_nginx.sh
```

**Option B: Manual setup**

1. Edit nginx config:
   ```bash
   sudo nano /etc/nginx/sites-available/scalper-agent
   ```

2. Add this configuration (before the root `location /` block):
   ```nginx
   # Liquidation Heatmap API (port 8004)
   location /liquidation-heatmap {
       proxy_pass http://127.0.0.1:8004;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }

   location /api/heatmap {
       proxy_pass http://127.0.0.1:8004/api/heatmap;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```

3. Test and reload:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Step 3: Verify

```bash
# Test UI
curl https://api.wagmi-global.eu/liquidation-heatmap

# Test API
curl https://api.wagmi-global.eu/api/heatmap/BTCUSDT

# Test symbols
curl https://api.wagmi-global.eu/api/heatmap/symbols
```

---

## 📍 URLs

### Production (Wagmi)
- **UI**: `https://api.wagmi-global.eu/liquidation-heatmap`
- **API**: `https://api.wagmi-global.eu/api/heatmap/BTCUSDT`
- **Best Cluster**: `https://api.wagmi-global.eu/api/heatmap/BTCUSDT/best`
- **Symbols**: `https://api.wagmi-global.eu/api/heatmap/symbols`

### Local Development
- **UI**: `http://localhost:8004`
- **API**: `http://localhost:8004/api/heatmap/BTCUSDT`
- **Docs**: `http://localhost:8004/docs`

---

## 🔧 Systemd Service (Optional)

Create `/etc/systemd/system/liquidation-heatmap.service`:

```ini
[Unit]
Description=Liquidation Heatmap API
After=network.target

[Service]
Type=simple
User=botadmin
WorkingDirectory=/home/botadmin/memecoin-perp-strategies
ExecStart=/usr/bin/python3 api/liquidation_heatmap_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable liquidation-heatmap
sudo systemctl start liquidation-heatmap
sudo systemctl status liquidation-heatmap
```

---

## 🐛 Troubleshooting

### 502 Bad Gateway
- Check API is running: `ps aux | grep liquidation_heatmap`
- Check port 8004: `netstat -tuln | grep 8004`
- Check nginx config: `sudo nginx -t`

### 404 Not Found
- Verify nginx config includes `/liquidation-heatmap` location
- Check nginx reloaded: `sudo systemctl reload nginx`
- Check nginx logs: `sudo tail -f /var/log/nginx/error.log`

### WebSocket Not Connecting
- Check firewall allows outbound to `wss://fstream.binance.com`
- Check API logs: `tail -f /tmp/liquidation_heatmap.log`

---

## ✅ Summary

- ✅ Port changed to **8004**
- ✅ Nginx config created (`nginx_liquidation_heatmap.conf`)
- ✅ Setup script created (`setup_liquidation_heatmap_nginx.sh`)
- ✅ Documentation updated
- ✅ Ready to deploy!

**Access at**: `https://api.wagmi-global.eu/liquidation-heatmap`
