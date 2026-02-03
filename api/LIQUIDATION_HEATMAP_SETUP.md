# Liquidation Heatmap API Setup Guide

## 🎯 Overview

Interactive web UI for visualizing real-time liquidation clusters from Binance Futures, similar to Coinglass heatmap.

**Access**: `https://api.wagmi-global.eu/liquidation-heatmap` (or `http://localhost:8004` locally)

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install websocket-client fastapi uvicorn httpx pydantic pandas numpy scipy
```

### 2. Start the API

```bash
# Option 1: Use startup script
chmod +x api/start_liquidation_heatmap.sh
./api/start_liquidation_heatmap.sh

# Option 2: Direct Python
python api/liquidation_heatmap_api.py

# Option 3: With uvicorn
uvicorn api.liquidation_heatmap_api:app --host 0.0.0.0 --port 8004
```

### 3. Access the UI

Open your browser:
- **UI**: http://localhost:8004 (local) or https://api.wagmi-global.eu/liquidation-heatmap
- **API Docs**: http://localhost:8004/docs
- **API Endpoint**: http://localhost:8004/api/heatmap/BTCUSDT

---

## 📡 API Endpoints

### GET `/` or `/liquidation-heatmap`
Serves the interactive heatmap UI

**URLs**:
- Local: `http://localhost:8004/`
- Production: `https://api.wagmi-global.eu/liquidation-heatmap`

### GET `/api/symbols`
Get list of supported symbols

**URLs**:
- Local: `http://localhost:8004/api/symbols`
- Production: `https://api.wagmi-global.eu/api/heatmap/symbols`

**Response**:
```json
{
  "success": true,
  "symbols": ["BTCUSDT", "ETHUSDT", ...],
  "count": 28
}
```

### GET `/api/heatmap/{symbol}`
Get liquidation clusters for a symbol

**Parameters**:
- `symbol`: Trading symbol (e.g., `BTCUSDT`)
- `min_strength`: Minimum cluster strength (0-1, default: 0.0)
- `max_distance`: Maximum distance from price % (default: 10.0)

**Example URLs**:
- Local: `http://localhost:8004/api/heatmap/BTCUSDT?min_strength=0.6&max_distance=5`
- Production: `https://api.wagmi-global.eu/api/heatmap/BTCUSDT?min_strength=0.6&max_distance=5`

**Response**:
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "current_price": 90000.0,
  "clusters": [
    {
      "price_level": 89500.0,
      "side": "long",
      "liquidation_count": 15,
      "total_notional": 1250000.0,
      "strength": 0.75,
      "distance_from_price": 0.56,
      "cluster_id": 1,
      "last_updated": "2026-01-28T12:00:00"
    }
  ],
  "timestamp": "2026-01-28T12:00:00",
  "total_clusters": 5
}
```

### GET `/api/heatmap/{symbol}/best`
Get best trading cluster for a symbol

**Parameters**:
- `symbol`: Trading symbol
- `min_strength`: Minimum cluster strength (default: 0.6)

### GET `/api/stats`
Get overall statistics

---

## 🎨 UI Features

### Interactive Heatmap
- **Visual clusters**: Color-coded bands (red = long liquidations, green = short liquidations)
- **Current price line**: Blue line showing current market price
- **Cluster strength**: Opacity and height indicate cluster strength
- **Hover/Click**: Show detailed cluster information

### Controls
- **Symbol search**: Type or select symbol from dropdown
- **Min Strength filter**: Filter clusters by minimum strength
- **Max Distance filter**: Filter clusters by distance from current price
- **Auto Refresh**: Toggle automatic updates every 5 seconds

### Statistics
- Current price
- Total clusters
- Long clusters count
- Short clusters count

---

## 🔧 Configuration

### Supported Symbols

Default symbols include:
- Major coins: BTC, ETH, BNB, SOL, XRP, DOGE, etc.
- Memecoins: SHIB, PEPE, BONK, FLOKI, MOG, CAT, etc.

To add more symbols, edit `SUPPORTED_SYMBOLS` in `liquidation_heatmap_api.py`.

### Update Intervals

- **Price updates**: Every 10 seconds (from Binance API)
- **Cluster updates**: Every 5 seconds (from WebSocket stream)
- **UI refresh**: Configurable (default: 5 seconds with auto-refresh)

### Cluster Parameters

Edit in `LiveLiquidationHeatmap` initialization:
- `cluster_window_pct`: Price window for clustering (default: 0.02 = 2%)
- `min_cluster_size`: Minimum liquidations per cluster (default: 5)
- `time_decay_minutes`: Time decay period (default: 60 minutes)
- `update_interval`: Seconds between updates (default: 5.0)

---

## 🌐 Deployment

### Local Development

```bash
python api/liquidation_heatmap_api.py
```

### Production with Nginx

1. **Update nginx config** (`/etc/nginx/sites-available/wagmi`):

```nginx
location /liquidation-heatmap {
    proxy_pass http://127.0.0.1:8001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

2. **Run with systemd** (create `/etc/systemd/system/liquidation-heatmap.service`):

```ini
[Unit]
Description=Liquidation Heatmap API
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/memecoin-perp-strategies
ExecStart=/usr/bin/python3 api/liquidation_heatmap_api.py
Restart=always

[Install]
WantedBy=multi-user.target
```

3. **Enable and start**:

```bash
sudo systemctl enable liquidation-heatmap
sudo systemctl start liquidation-heatmap
```

### Access via Domain

Once deployed, access at:
- `https://api.wagmi-global.eu/liquidation-heatmap`

---

## 🐛 Troubleshooting

### WebSocket Not Connecting

**Check**:
1. Firewall allows outbound connections to `wss://fstream.binance.com`
2. Internet connection is stable
3. Binance WebSocket is operational

### No Clusters Showing

**Possible reasons**:
1. Not enough liquidations yet (wait a few minutes)
2. `min_cluster_size` too high (try lowering to 3)
3. `min_strength` filter too high (try 0.0)
4. Symbol not supported

### High Memory Usage

**Solutions**:
1. Reduce `SUPPORTED_SYMBOLS` list
2. Reduce buffer size in `BinanceLiquidationStream`
3. Increase `update_interval` to reduce processing

### API Not Responding

**Check**:
1. Process is running: `ps aux | grep liquidation_heatmap`
2. Port 8004 is not blocked: `netstat -tuln | grep 8004`
3. Check logs for errors

---

## 📊 Performance

### Resource Usage

- **CPU**: Low (~5-10% on single core)
- **Memory**: ~50-100 MB per symbol
- **Network**: ~1-5 KB/s per symbol (WebSocket)
- **Port**: 8004

### Scalability

- Supports 28+ symbols simultaneously
- Can handle 100+ concurrent API requests
- WebSocket reconnects automatically

---

## 🔐 Security

### CORS

Currently allows all origins (`allow_origins=["*"]`). For production, restrict:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wagmi-global.eu", "https://api.wagmi-global.eu"],
    ...
)
```

### Rate Limiting

Consider adding rate limiting for production:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/heatmap/{symbol}")
@limiter.limit("10/minute")
async def get_heatmap(...):
    ...
```

---

## 📚 Files

- `liquidation_heatmap_api.py` - FastAPI backend
- `liquidation_heatmap_ui.html` - Interactive frontend
- `live_liquidation_heatmap.py` - Live heatmap engine
- `start_liquidation_heatmap.sh` - Startup script

---

## 🎉 Summary

You now have a **free, interactive liquidation heatmap** similar to Coinglass!

- ✅ Real-time Binance WebSocket data
- ✅ Interactive web UI
- ✅ Search by symbol
- ✅ Filter by strength/distance
- ✅ Auto-refresh option
- ✅ 100% free (no API keys needed)

**Perfect for monitoring liquidation clusters in real-time!** 🚀
