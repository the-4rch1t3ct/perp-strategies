# Agent Decision Analysis

## Decision Summary

**Agent Action**: `nothing`  
**Reason**: Missing required indicators (MACD Histogram, Volume Ratio, Volume Percentile, Trend Strength, Price Position, Signal Strength)

## Root Cause Analysis

### ✅ Indicators Available in CTX.ind:
- `atr14_5m` ✅
- `ema12_5m` ✅
- `ema36_5m` ✅
- `ma36_5m` ✅ (Volume MA - note: prompt asks for `volume_ma36_5m` but data provides `ma36_5m`)
- `mom12_5m` ✅
- `rsi14_5m` ✅
- `volume_5m` ✅

### ❌ Indicators Missing from CTX.ind:
- `macd_5m` ❌ **CRITICAL** - MACD data exists in raw indicators but NOT in CTX.ind format
- `high20_5m` ❌ **CRITICAL** - Not provided at all
- `low20_5m` ❌ **CRITICAL** - Not provided at all

### ⚠️ Calculated Values (Agent Says Missing):

The agent reports missing these, but some CAN be calculated:

1. **Volume Ratio** ⚠️ **CAN CALCULATE**
   - Formula: `Volume Ratio = volume_5m[0] / ma36_5m[0]`
   - Data available: ✅ `volume_5m` and `ma36_5m` are both present
   - **Issue**: Agent may not realize this is calculable

2. **Trend Strength** ⚠️ **CAN CALCULATE**
   - Formula: `Trend Strength = |ema12_5m[0] - ema36_5m[0]| / ema36_5m[0]`
   - Data available: ✅ Both EMAs are present
   - **Issue**: Agent may not realize this is calculable

3. **MACD Histogram** ❌ **CANNOT CALCULATE**
   - Raw MACD data exists in indicators object with `valueMACDHist` array
   - But NOT in `CTX.ind[symbol]["macd_5m"]` format
   - **Issue**: Data format mismatch - MACD exists but not in expected location

4. **Price Position** ❌ **CANNOT CALCULATE**
   - Formula: `(Close - low20_5m) / (high20_5m - low20_5m)`
   - Missing: `high20_5m` and `low20_5m` not provided
   - **Issue**: Required indicators not provided by system

5. **Volume Percentile** ❌ **CANNOT CALCULATE**
   - Requires: Historical volume data (last 100 periods) to rank current volume
   - Available: Only current `volume_5m[0]` and `ma36_5m[0]` (average)
   - **Issue**: Need historical volume array, not just current value

6. **Signal Strength** ⚠️ **CANNOT CALCULATE** (depends on above)
   - Requires: Momentum, Volume Ratio, Trend Strength, RSI
   - Missing dependencies: MACD Histogram (for filter check), Price Position

## Issues Identified

### Issue 1: MACD Data Format Mismatch
**Problem**: MACD data exists in raw indicators but not in CTX.ind format
- Raw indicators have: `exchange=binancefutures|indicator=macd|...|symbol=BAN` with `valueMACDHist`
- Agent expects: `CTX.ind["BAN"]["macd_5m"]` with histogram value
- **Solution**: System needs to transform MACD data into CTX.ind format

### Issue 2: Missing High20/Low20 Indicators
**Problem**: `high20_5m` and `low20_5m` are not provided
- Required for: Price Position calculation
- **Solution**: System needs to provide `max`/`min` indicators over 20 periods

### Issue 3: Volume Percentile Cannot Be Calculated
**Problem**: Prompt requires "Volume Percentile > 25" but no historical volume data
- Need: Array of last 100 periods of volume to calculate percentile rank
- Have: Only current volume value and 36-period MA
- **Solution Options**:
  - Option A: Provide historical volume array (100 periods)
  - Option B: Remove Volume Percentile requirement from prompt
  - Option C: Use Volume Ratio as proxy (already > 1.08 requirement)

### Issue 4: Agent Doesn't Recognize Calculable Values
**Problem**: Agent reports "missing" Volume Ratio and Trend Strength, but these CAN be calculated
- **Solution**: Update prompt to explicitly state these are CALCULATED, not raw indicators

### Issue 5: Volume MA Naming Inconsistency
**Problem**: Prompt asks for `volume_ma36_5m` but data provides `ma36_5m`
- **Solution**: Either update prompt to match data, or update data to match prompt

## Recommended Fixes

### Fix 1: Update Prompt to Clarify Calculated Values

Add explicit instructions that some values are calculated:

```
CALCULATED VALUES (not raw indicators - compute these):
- Volume Ratio = volume_5m[0] / ma36_5m[0]
- Trend Strength = |ema12_5m[0] - ema36_5m[0]| / ema36_5m[0]
- Price Position = (Close - low20_5m[0]) / (high20_5m[0] - low20_5m[0])
- Signal Strength = (see formula above)
```

### Fix 2: Fix MACD Data Format

System needs to provide MACD histogram in CTX.ind format:
- Current: Raw indicators have `valueMACDHist` array
- Needed: `CTX.ind[symbol]["macd_5m"] = [histogram_value]`

### Fix 3: Provide High20/Low20 Indicators

System needs to add:
- `high20_5m`: Highest high over 20 periods
- `low20_5m`: Lowest low over 20 periods

### Fix 4: Handle Volume Percentile

**Option A** (Recommended): Remove Volume Percentile requirement
- Replace with: "Volume Ratio > 1.08" (already required)
- Simpler and doesn't need historical data

**Option B**: Provide historical volume array
- Add: `volume_history_5m` array with last 100 periods
- Agent calculates percentile rank

### Fix 5: Fix Volume MA Naming

Update prompt to match data:
- Change: `volume_ma36_5m` → `ma36_5m`
- Or update data to match prompt

## Current Status

**Agent Behavior**: ✅ CORRECT - Agent correctly identifies missing data and refuses to trade

**System Status**: ❌ INCOMPLETE - Missing 3 critical indicators:
1. MACD (format issue)
2. High20/Low20 (not provided)
3. Volume Percentile data (not provided)

**Next Steps**:
1. Fix MACD data format in system
2. Add High20/Low20 indicators to system
3. Either remove Volume Percentile requirement or provide historical volume data
4. Update prompt to clarify calculated vs raw indicators
