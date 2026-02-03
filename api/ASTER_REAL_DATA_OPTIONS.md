# Aster batch: where to get real cluster/confidence data

Aster’s **public REST API** does **not** expose open interest or liquidation levels. The Aster batch uses **Binance (primary) or Hyperliquid** clusters only (no synthetic). Symbols without real cluster data are omitted. XAG and XAU are not in the Aster symbol list.

---

## Option 1: Aster WebSocket – real liquidations (reactive)

**Source:** Aster’s own WebSocket streams.

From [Aster Futures API](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api.md):

- **Liquidation order stream (per symbol):** `wss://fstream.asterdex.com/ws/<symbol>@forceOrder`
- **All market liquidations:** `wss://fstream.asterdex.com/stream?streams=!forceOrder@arr`

**Payload shape:** `forceOrder` events with symbol, side (BUY/SELL), price, quantity, etc. when a liquidation actually happens.

**How to use it:**
- Subscribe and buffer liquidation events (e.g. by symbol and price bucket).
- Build **clusters from where liquidations actually occurred** on Aster (price levels + volume/count).
- Derive **confidence** from recent liquidation frequency/size at each level (e.g. more liquidations → stronger cluster → higher conf).

**Pros:** Real Aster data; confidence reflects actual Aster liquidations.  
**Cons:** Reactive (after liquidations), not predictive OI; requires a persistent WebSocket and stateful aggregation.

---

## Option 2: Hybrid – Aster prices + Binance (or HL) clusters

**Sources:**
- **Prices (and thus entry/TP/SL):** Aster REST (`/fapi/v1/ticker/price`, `/fapi/v1/premiumIndex`) so levels match the venue you trade on.
- **Clusters / confidence:** Binance (main batch) or Hyperliquid batch – OI-based predictive levels and strength.

**Implementation idea:**
- For each symbol, keep fetching **prices from Aster** (as now).
- For symbols that **exist on Binance** (e.g. ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, BCHUSDT, LINKUSDT, XMRUSDT), pull **liquidation levels and strength** from the existing Binance heatmap (or Hyperliquid). Use those levels with **Aster’s price** to build `signal` (entry, tp, sl, **conf**).
- For **Aster-only symbols** (ASTERUSDT, HYPEUSDT, SUIUSDT, XAGUSDT, XAUUSDT, PUMPUSDT), no Binance/HL data exists → keep **synthetic levels** (current behaviour) or add Option 1 (Aster liquidation stream) later.

**Pros:** Real, varying confidence for overlapping symbols; no change to how you get Aster prices.  
**Cons:** Clusters are from another venue (Binance/HL), not Aster’s own order book; Aster-only symbols still need synthetic or Option 1.

---

## Option 3: Ask Aster for OI / liquidation-level API

You can request from Aster (e.g. via support or API docs / GitHub):
- A **public open interest** endpoint (e.g. total OI, ideally long/short per symbol).
- Any **liquidation level or risk** endpoint they might have (even if minimal).

If they add it, we could then drive clusters and confidence from Aster only (similar to Binance/HL).

---

## Recommendation

- **Short term:** Implement **Option 2 (hybrid)** for symbols that exist on Binance (or HL): Aster for price, Binance/HL for clusters and confidence. Keeps entry/TP/SL on Aster, adds real `conf` where the data exists.
- **Medium term:** Add **Option 1 (Aster liquidation WebSocket)** to build real Aster-only clusters and confidence for all symbols (including ASTER, HYPE, SUI, XAG, XAU, PUMP), and optionally blend with hybrid where you want predictive OI for overlapping symbols.
