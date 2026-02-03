# Liquidation Heatmap - Quick Start

## 🚀 Start in 3 Steps

### 1. Install Dependencies

```bash
pip install websocket-client fastapi uvicorn httpx pydantic pandas numpy scipy
```

### 2. Start the API

```bash
python api/liquidation_heatmap_api.py
```

### 3. Open Browser

Visit: **http://localhost:8004** (local) or **https://api.wagmi-global.eu/liquidation-heatmap** (production)

---

## 🎯 Features

- ✅ **Interactive heatmap** (like Coinglass)
- ✅ **Search by symbol** (BTCUSDT, ETHUSDT, etc.)
- ✅ **Real-time updates** (auto-refresh every 5 seconds)
- ✅ **Filter clusters** (by strength, distance)
- ✅ **100% free** (no API keys needed)

---

## 📡 API Endpoints

**Local (port 8004)**:
- **UI**: `http://localhost:8004/`
- **Clusters**: `http://localhost:8004/api/heatmap/BTCUSDT`
- **Best Cluster**: `http://localhost:8004/api/heatmap/BTCUSDT/best`
- **Symbols**: `http://localhost:8004/api/symbols`
- **Docs**: `http://localhost:8004/docs`

**Production (wagmi-global.eu)**:
- **UI**: `https://api.wagmi-global.eu/liquidation-heatmap`
- **Clusters**: `https://api.wagmi-global.eu/api/heatmap/BTCUSDT`
- **Best Cluster**: `https://api.wagmi-global.eu/api/heatmap/BTCUSDT/best`
- **Symbols**: `https://api.wagmi-global.eu/api/heatmap/symbols`

---

## 🌐 Deploy to api.wagmi-global.eu

1. **Update nginx** using setup script:
   ```bash
   chmod +x api/setup_liquidation_heatmap_nginx.sh
   sudo ./api/setup_liquidation_heatmap_nginx.sh
   ```
   Or manually add config from `api/nginx_liquidation_heatmap.conf` to proxy:
   - `/liquidation-heatmap` → `http://127.0.0.1:8004`
   - `/api/heatmap` → `http://127.0.0.1:8004/api/heatmap`

2. **Run with systemd** (see `LIQUIDATION_HEATMAP_SETUP.md`)

3. **Access at**: `https://api.wagmi-global.eu/liquidation-heatmap`

---

## 📚 Full Docs

See `LIQUIDATION_HEATMAP_SETUP.md` for complete setup guide.
