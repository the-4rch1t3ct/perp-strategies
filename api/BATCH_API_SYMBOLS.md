# Batch API Supported Symbols

## ✅ **Supported Symbols** (16 total)

The batch API now supports these symbols:

1. **ETHUSDT** - Ethereum
2. **SOLUSDT** - Solana
3. **BNBUSDT** - Binance Coin
4. **XRPUSDT** - Ripple
5. **TRXUSDT** - Tron
6. **DOGEUSDT** - Dogecoin
7. **ADAUSDT** - Cardano
8. **BCHUSDT** - Bitcoin Cash
9. **LINKUSDT** - Chainlink
10. **XMRUSDT** - Monero
11. **XLMUSDT** - Stellar
12. **ZECUSDT** - Zcash
13. **HYPEUSDT** - Hyperliquid
14. **LTCUSDT** - Litecoin
15. **SUIUSDT** - Sui
16. **AVAXUSDT** - Avalanche

---

## 📡 **Usage**

### Request Format:

The batch API accepts symbols in multiple formats - both will work:

```json
{
  "symbols": ["ETH", "SOL", "BNB"],
  "min_strength": 0.6,
  "max_distance": 3.0
}
```

**OR**

```json
{
  "symbols": ["ETHUSDT", "SOLUSDT", "BNBUSDT"],
  "min_strength": 0.6,
  "max_distance": 3.0
}
```

**Symbol Normalization:**
- `"ETH"` → `"ETHUSDT"`
- `"ETHUSDT"` → `"ETHUSDT"` (unchanged)
- `"ETH/USDT"` → `"ETHUSDT"`
- Case insensitive: `"eth"` → `"ETHUSDT"`

---

## 🎯 **Example Request**

```bash
curl -X POST https://api.wagmi-global.eu/api/trade/batch \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["ETH", "SOL", "BNB", "XRP", "TRX", "DOGE", "ADA", "BCH", "LINK", "XMR", "XLM", "ZEC", "HYPE", "LTC", "SUI", "AVAX"],
    "min_strength": 0.6,
    "max_distance": 3.0
  }'
```

---

## ✅ **Response**

Returns trading data for all requested symbols that are supported:

```json
{
  "results": {
    "ETHUSDT": {
      "signal": {"dir": "LONG", "entry": 2450.30, "sl": 2401.29, "tp": 2462.00, "conf": 0.75, "rr": 2.4},
      "levels": {"support": [2400.00], "resistance": [2462.00]},
      "sentiment": {"bias": "BULLISH", "lsr": 1.12, "oi": 2500000000.0},
      "clusters": {"best": {"price": 2462.00, "side": "short", "str": 0.75, "dist": 0.48}, "count": 5}
    },
    "SOLUSDT": {
      "signal": {"dir": "NEUTRAL", "entry": null, "sl": null, "tp": null, "conf": 0.0, "rr": null},
      "levels": {"support": [140.00], "resistance": [145.00]},
      "sentiment": {"bias": "NEUTRAL", "lsr": 1.0, "oi": 800000000.0},
      "clusters": {"best": null, "count": 3}
    }
  },
  "ts": "2026-01-28T22:30:00"
}
```

---

## ⚠️ **Notes**

- Symbols not in the supported list will be **skipped** (not included in response)
- All symbols are normalized to Binance Futures format (`SYMBOLUSDT`)
- The API will start tracking these symbols when initialized
- Data updates every 5 seconds for prices, 30 seconds for OI

---

## 🔄 **Restart Required**

After updating symbols, restart the API service to start tracking the new symbols:

```bash
sudo systemctl restart liquidation-heatmap-api
```

Or if running manually:
```bash
cd /home/botadmin/memecoin-perp-strategies
source venv/bin/activate
python -m api.liquidation_heatmap_api
```
