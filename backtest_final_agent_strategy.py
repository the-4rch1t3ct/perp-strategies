#!/usr/bin/env python3
"""
Backtest for Final Agent Strategy (AGENT_PROMPT_COMPACT.md)
Implements exact strategy from the agent prompt
"""

import pandas as pd
import numpy as np
import glob
import os
from pathlib import Path
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))

class PositionSide(Enum):
    LONG = 1
    SHORT = -1

@dataclass
class Position:
    symbol: str
    side: PositionSide
    entry_price: float
    entry_time: pd.Timestamp
    size: float
    leverage: float
    signal_strength: float
    atr: float
    funding_rate: Optional[float] = None
    oi_change_pct: Optional[float] = None
    highest_price: float = 0.0
    lowest_price: float = 0.0
    trend_reversal_count: int = 0  # Track consecutive trend reversal signals

class FinalAgentStrategy:
    """Implements the exact strategy from AGENT_PROMPT_COMPACT.md"""
    
    def __init__(self):
        self.name = "FinalAgentStrategy"
        
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators"""
        df = data.copy()
        
        # EMA
        df['ema12_5m'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema36_5m'] = df['close'].ewm(span=36, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi14_5m'] = 100 - (100 / (1 + rs))
        
        # Momentum (12 periods)
        df['mom12_5m'] = df['close'].pct_change(12)
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr14_5m'] = true_range.rolling(window=14).mean()
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df['macd_5m'] = macd_line - signal_line  # Histogram
        
        # Volume
        df['volume_5m'] = df['volume']
        df['ma36_5m'] = df['volume'].rolling(window=36).mean()
        
        # Calculated values
        df['volume_ratio'] = df['volume_5m'] / df['ma36_5m']
        df['trend_strength'] = np.abs(df['ema12_5m'] - df['ema36_5m']) / df['ema36_5m']

        # External data (optional): Open Interest and Funding Rate
        oi_col = None
        for col in ['oi', 'open_interest', 'openInterest']:
            if col in df.columns:
                oi_col = col
                break
        if oi_col:
            df['oi'] = pd.to_numeric(df[oi_col], errors='coerce')
            df['oi_change_pct'] = df['oi'].pct_change()
            df['oi_change_pct'] = df['oi_change_pct'].replace([np.inf, -np.inf], np.nan)
        else:
            df['oi'] = np.nan
            df['oi_change_pct'] = np.nan

        fr_col = None
        for col in ['fr', 'funding_rate', 'fundingRate']:
            if col in df.columns:
                fr_col = col
                break
        if fr_col:
            df['fr'] = pd.to_numeric(df[fr_col], errors='coerce')
        else:
            df['fr'] = np.nan
        
        return df
    
    def calculate_signal_strength(self, row: pd.Series, side: str) -> float:
        """Calculate signal strength"""
        momentum = row['mom12_5m']
        volume_ratio = row['volume_ratio']
        trend_strength = row['trend_strength']
        rsi = row['rsi14_5m']
        
        if side == 'LONG':
            mom_str = min(momentum / (0.005 * 2.5), 1.0) if momentum > 0 else 0
            vol_str = min((volume_ratio - 1.0) / 1.5, 1.0) if volume_ratio > 1.0 else 0
            trend_str = min(trend_strength / 0.3, 1.0)
            rsi_str = max(0, min((rsi - 50) / 15, 1.0))
        else:  # SHORT
            mom_str = min(abs(momentum) / (0.005 * 2.5), 1.0) if momentum < 0 else 0
            vol_str = min((volume_ratio - 1.0) / 1.5, 1.0) if volume_ratio > 1.0 else 0
            trend_str = min(trend_strength / 0.3, 1.0)
            rsi_str = max(0, min((50 - rsi) / 15, 1.0))
        
        base_signal = 0.35 * mom_str + 0.25 * vol_str + 0.25 * trend_str + 0.15 * rsi_str

        # Optional adjustments using OI change and funding rate
        signal = base_signal
        oi_change_pct = row.get('oi_change_pct', np.nan)
        if pd.notna(oi_change_pct) and oi_change_pct > 0:
            oi_str = min(oi_change_pct / 0.004, 1.0)
            signal += 0.10 * oi_str

        funding_rate = row.get('fr', np.nan)
        if pd.notna(funding_rate):
            if side == 'LONG':
                funding_str = max(min((-funding_rate) / 0.0006, 1.0), -1.0)
            else:
                funding_str = max(min((funding_rate) / 0.0006, 1.0), -1.0)
            signal += 0.05 * funding_str

        # Clamp to [0, 1]
        signal = max(min(signal, 1.0), 0.0)
        return signal
    
    def get_leverage(self, signal_strength: float) -> float:
        """Get leverage based on signal strength (updated thresholds)"""
        if signal_strength >= 0.75:  # Increased from 0.70
            return 20.0
        elif signal_strength >= 0.60:  # Increased from 0.55
            return 15.0
        elif signal_strength >= 0.45:  # Increased from 0.40
            return 10.0
        return 0.0
    
    def check_long_entry(self, row: pd.Series) -> Tuple[bool, float]:
        """Check if LONG entry conditions are met"""
        # Check for NaN values
        required_cols = ['ema12_5m', 'ema36_5m', 'mom12_5m', 'rsi14_5m', 'volume_ratio', 
                        'macd_5m', 'trend_strength', 'atr14_5m']
        if any(pd.isna(row[col]) for col in required_cols):
            return False, 0.0

        # 1. EMA_fast > EMA_slow
        if not (row['ema12_5m'] > row['ema36_5m']):
            return False, 0.0
        
        # 2. Momentum > 0.005 (increased from 0.004 for stronger signals)
        if not (row['mom12_5m'] > 0.005):
            return False, 0.0
        
        # 3. RSI > 52 AND RSI < 60 (further tightened for stronger momentum)
        if not (row['rsi14_5m'] > 52 and row['rsi14_5m'] < 60):
            return False, 0.0
        
        # 4. Volume Ratio > 1.12 (slightly loosened for more trades)
        if not (row['volume_ratio'] > 1.12):
            return False, 0.0
        
        # 5. Require ALL 3 filters: Trend Strength > 0.0015, Volume Ratio > 1.12, MACD Histogram > 0
        if not (row['trend_strength'] > 0.0015 and row['volume_ratio'] > 1.12 and row['macd_5m'] > 0):
            return False, 0.0
        
        # 6. |Momentum| > 0.003 (increased from 0.002)
        if not (abs(row['mom12_5m']) > 0.003):
            return False, 0.0
        
        # 7. Signal Strength > 0.45 (increased for highest quality entries)
        signal_strength = self.calculate_signal_strength(row, 'LONG')
        if signal_strength <= 0.45:
            return False, 0.0

        # 8. If OI/FR available: OI Change % >= 0.001 AND fr <= 0.0005
        # Only apply filters if we have valid OI change data (not constant/zero)
        oi_change_pct = row.get('oi_change_pct', np.nan)
        funding_rate = row.get('fr', np.nan)
        
        # OI change filter: only apply if we have meaningful change data
        # If OI change is NaN or 0 (constant OI), treat as neutral (don't block)
        if pd.notna(oi_change_pct) and abs(oi_change_pct) > 1e-10:  # Non-zero change
            if oi_change_pct < 0.001:
                return False, 0.0
        
        # Funding rate filter: apply if available
        if pd.notna(funding_rate) and funding_rate > 0.0005:
            return False, 0.0
        
        return True, signal_strength
    
    def check_short_entry(self, row: pd.Series) -> Tuple[bool, float]:
        """Check if SHORT entry conditions are met"""
        # Check for NaN values
        required_cols = ['ema12_5m', 'ema36_5m', 'mom12_5m', 'rsi14_5m', 'volume_ratio', 
                        'macd_5m', 'trend_strength', 'atr14_5m']
        if any(pd.isna(row[col]) for col in required_cols):
            return False, 0.0

        # 1. EMA_fast < EMA_slow
        if not (row['ema12_5m'] < row['ema36_5m']):
            return False, 0.0
        
        # 2. Momentum < -0.005 (increased from -0.004 for stronger signals)
        if not (row['mom12_5m'] < -0.005):
            return False, 0.0
        
        # 3. RSI < 48 AND RSI > 40 (further tightened for stronger momentum)
        if not (row['rsi14_5m'] < 48 and row['rsi14_5m'] > 40):
            return False, 0.0
        
        # 4. Volume Ratio > 1.12 (slightly loosened for more trades)
        if not (row['volume_ratio'] > 1.12):
            return False, 0.0
        
        # 5. Require ALL 3 filters: Trend Strength > 0.0015, Volume Ratio > 1.12, MACD Histogram < 0
        if not (row['trend_strength'] > 0.0015 and row['volume_ratio'] > 1.12 and row['macd_5m'] < 0):
            return False, 0.0
        
        # 6. |Momentum| > 0.003 (increased from 0.002)
        if not (abs(row['mom12_5m']) > 0.003):
            return False, 0.0
        
        # 7. Signal Strength > 0.45 (increased for highest quality entries)
        signal_strength = self.calculate_signal_strength(row, 'SHORT')
        if signal_strength <= 0.45:
            return False, 0.0

        # 8. If OI/FR available: OI Change % >= 0.001 AND fr >= -0.0005
        # Only apply filters if we have valid OI change data (not constant/zero)
        oi_change_pct = row.get('oi_change_pct', np.nan)
        funding_rate = row.get('fr', np.nan)
        
        # OI change filter: only apply if we have meaningful change data
        # If OI change is NaN or 0 (constant OI), treat as neutral (don't block)
        if pd.notna(oi_change_pct) and abs(oi_change_pct) > 1e-10:  # Non-zero change
            if oi_change_pct < 0.001:
                return False, 0.0
        
        # Funding rate filter: apply if available
        if pd.notna(funding_rate) and funding_rate < -0.0005:
            return False, 0.0
        
        return True, signal_strength
    
    def check_exit(self, row: pd.Series, position: Position) -> Tuple[bool, str]:
        """Check exit conditions"""
        current_price = row['close']
        periods_held = (row.name - position.entry_time).total_seconds() / 300  # 5 minutes per period
        
        # Max hold: 72 periods (6 hours)
        if periods_held >= 72:
            return True, 'MAX_HOLD'
        
        # Stop Loss (tuned to 2.5×ATR)
        if position.side == PositionSide.LONG:
            if current_price <= position.entry_price - (2.5 * position.atr):
                return True, 'STOP_LOSS'
        else:  # SHORT
            if current_price >= position.entry_price + (2.5 * position.atr):
                return True, 'STOP_LOSS'
        
        # Take Profit (tuned to 2.5×ATR)
        if position.side == PositionSide.LONG:
            if current_price >= position.entry_price + (2.5 * position.atr):
                return True, 'TAKE_PROFIT'
        else:  # SHORT
            if current_price <= position.entry_price - (2.5 * position.atr):
                return True, 'TAKE_PROFIT'
        
        # Trailing Stop (after 1.0×ATR profit, less aggressive from 0.8×ATR to 1.0×ATR)
        if position.side == PositionSide.LONG:
            profit = current_price - position.entry_price
            if profit >= 1.0 * position.atr:
                trailing_stop = position.highest_price - (1.0 * position.atr)
                if current_price <= trailing_stop:
                    return True, 'TRAILING_STOP'
        else:  # SHORT
            profit = position.entry_price - current_price
            if profit >= 1.0 * position.atr:
                trailing_stop = position.lowest_price + (1.0 * position.atr)
                if current_price >= trailing_stop:
                    return True, 'TRAILING_STOP'

        
        # Trend Reversal (only trigger after minimum hold time of 6 periods = 30 minutes)
        # Require trend reversal to persist for 2 consecutive periods before exiting
        if periods_held >= 6:
            if position.side == PositionSide.LONG:
                # Require BOTH conditions for trend reversal (more conservative)
                if row['ema12_5m'] < row['ema36_5m'] and row['macd_5m'] < 0:
                    position.trend_reversal_count += 1
                    if position.trend_reversal_count >= 2:  # Must persist for 2 periods
                        return True, 'TREND_REVERSAL'
                else:
                    position.trend_reversal_count = 0  # Reset if conditions not met
            else:  # SHORT
                # Require BOTH conditions for trend reversal (more conservative)
                if row['ema12_5m'] > row['ema36_5m'] and row['macd_5m'] > 0:
                    position.trend_reversal_count += 1
                    if position.trend_reversal_count >= 2:  # Must persist for 2 periods
                        return True, 'TREND_REVERSAL'
                else:
                    position.trend_reversal_count = 0  # Reset if conditions not met
        else:
            position.trend_reversal_count = 0  # Reset if not enough time held
        
        return False, ''
    
    def calculate_pnl(self, position: Position, exit_price: float, fee_rate: float = 0.0001) -> float:
        """Calculate P&L for a trade"""
        notional = position.size * position.entry_price
        entry_fee = notional * fee_rate
        exit_fee = position.size * exit_price * fee_rate
        
        if position.side == PositionSide.LONG:
            price_change_pct = (exit_price - position.entry_price) / position.entry_price
        else:
            price_change_pct = (position.entry_price - exit_price) / position.entry_price
        
        # PnL with leverage
        margin = notional / position.leverage
        pnl = margin * price_change_pct * position.leverage - entry_fee - exit_fee
        
        return pnl

def backtest_strategy(data_dict: Dict[str, pd.DataFrame], 
                     initial_capital: float = 10000.0,
                     max_positions: int = 4,
                     fee_rate: float = 0.0001) -> Dict:
    """Backtest the final agent strategy"""
    
    strategy = FinalAgentStrategy()
    capital = initial_capital
    positions: Dict[str, Position] = {}
    all_trades = []
    equity_curve = [capital]
    
    # Process each symbol
    for symbol, data in data_dict.items():
        print(f"Processing {symbol}...")
        
        # Calculate indicators
        df = strategy.calculate_indicators(data)
        
        # Skip if not enough data
        if len(df) < 100:
            continue
        
        # Process each candle
        for idx, row in df.iterrows():
            # Update existing positions for this symbol
            if symbol in positions:
                position = positions[symbol]
                
                # Update highest/lowest price for trailing stop
                if position.side == PositionSide.LONG:
                    position.highest_price = max(position.highest_price, row['close'])
                else:
                    position.lowest_price = min(position.lowest_price, row['close'])
                
                should_exit, exit_reason = strategy.check_exit(row, position)
                
                if should_exit:
                    # Close position
                    exit_price = row['close']
                    pnl = strategy.calculate_pnl(position, exit_price, fee_rate)
                    
                    # Return margin and add PnL
                    margin = (position.size * position.entry_price) / position.leverage
                    capital += margin + pnl
                    
                    all_trades.append({
                        'symbol': symbol,
                        'entry_time': position.entry_time,
                        'exit_time': idx,
                        'side': str(position.side),
                        'entry_price': position.entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'exit_reason': exit_reason,
                        'leverage': position.leverage,
                        'signal_strength': position.signal_strength,
                        'duration_periods': (idx - position.entry_time).total_seconds() / 300
                    })
                    del positions[symbol]
            
            # Check for new entries (only if we have capacity)
            if len(positions) < max_positions and symbol not in positions:
                # Check LONG entry
                can_long, signal_strength_long = strategy.check_long_entry(row)
                if can_long:
                    leverage = strategy.get_leverage(signal_strength_long)
                    # Use current capital (which compounds) for position sizing
                    # Reduced base from 25% to 20% to lower risk
                    position_size_pct = 0.20 * signal_strength_long
                    notional = capital * position_size_pct * leverage
                    size = notional / row['close']
                    margin = notional / leverage
                    
                    # Check if we have enough capital (reserve 10% for fees/slippage)
                    if margin <= capital * 0.9:
                        positions[symbol] = Position(
                            symbol=symbol,
                            side=PositionSide.LONG,
                            entry_price=row['close'],
                            entry_time=idx,
                            size=size,
                            leverage=leverage,
                            signal_strength=signal_strength_long,
                            atr=row['atr14_5m'],
                            highest_price=row['close'],
                            trend_reversal_count=0
                        )
                        capital -= margin  # Lock margin
                    continue
                
                # Check SHORT entry
                can_short, signal_strength_short = strategy.check_short_entry(row)
                if can_short:
                    leverage = strategy.get_leverage(signal_strength_short)
                    # Use current capital (which compounds) for position sizing
                    # Reduced base from 25% to 20% to lower risk
                    position_size_pct = 0.20 * signal_strength_short
                    notional = capital * position_size_pct * leverage
                    size = notional / row['close']
                    margin = notional / leverage
                    
                    # Check if we have enough capital (reserve 10% for fees/slippage)
                    if margin <= capital * 0.9:
                        positions[symbol] = Position(
                            symbol=symbol,
                            side=PositionSide.SHORT,
                            entry_price=row['close'],
                            entry_time=idx,
                            size=size,
                            leverage=leverage,
                            signal_strength=signal_strength_short,
                            atr=row['atr14_5m'],
                            lowest_price=row['close'],
                            trend_reversal_count=0
                        )
                        capital -= margin  # Lock margin
            
            # Note: Equity curve will be calculated at end since we process symbols sequentially
            # For now, just track capital changes
            pass
    
    # Close any remaining positions at end
    for symbol, position in list(positions.items()):
        # Get last row from the symbol's dataframe
        for sym, df in data_dict.items():
            if sym == symbol:
                # Recalculate indicators to get latest ATR
                df_with_indicators = strategy.calculate_indicators(df)
                last_row = df_with_indicators.iloc[-1]
                exit_price = last_row['close']
                pnl = strategy.calculate_pnl(position, exit_price, fee_rate)
                
                # Return margin and add PnL
                margin = (position.size * position.entry_price) / position.leverage
                capital += margin + pnl
                
                all_trades.append({
                    'symbol': symbol,
                    'entry_time': position.entry_time,
                    'exit_time': df.index[-1],
                    'side': str(position.side),
                    'entry_price': position.entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': 'END_OF_DATA',
                    'leverage': position.leverage,
                    'signal_strength': position.signal_strength,
                    'duration_periods': (df.index[-1] - position.entry_time).total_seconds() / 300
                })
                break
    
    # Calculate metrics
    if not all_trades:
        return {'error': 'No trades generated', 'capital': capital}
    
    trades_df = pd.DataFrame(all_trades)
    total_pnl = trades_df['pnl'].sum()
    
    # Final capital should be initial + all PnL
    # Capital already includes returned margins and PnL from closed positions
    total_return = ((capital - initial_capital) / initial_capital) * 100
    
    winning_trades = trades_df[trades_df['pnl'] > 0]
    win_rate = len(winning_trades) / len(trades_df) * 100 if len(trades_df) > 0 else 0
    
    avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
    losing_trades = trades_df[trades_df['pnl'] < 0]
    avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
    
    # Calculate Sharpe ratio
    if len(trades_df) > 1:
        returns = trades_df['pnl'] / initial_capital
        sharpe = np.sqrt(252 * 288) * returns.mean() / returns.std() if returns.std() > 0 else 0  # 288 5m periods per day
    else:
        sharpe = 0
    
    # Max drawdown
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.expanding().max()
    drawdown = (equity_series - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    
    return {
        'total_trades': len(trades_df),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'final_capital': capital,
        'total_return_pct': total_return,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
        'sharpe_ratio': sharpe,
        'max_drawdown_pct': max_drawdown,
        'trades': trades_df.to_dict('records')
    }

def load_5m_data(last_n_days: Optional[int] = None) -> Dict[str, pd.DataFrame]:
    """Load all 5-minute CSV files, optionally filtered to last N days"""
    data_dict = {}
    csv_files = glob.glob('data/*_5m.csv')
    
    # Calculate cutoff date if filtering by days
    cutoff_date = None
    if last_n_days:
        cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=last_n_days)
    
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            
            # Filter to last N days if specified
            if cutoff_date is not None and len(df) > 0:
                df = df[df.index >= cutoff_date]
            
            if len(df) >= 100:  # Still need minimum data for indicators
                symbol_key = os.path.basename(filepath).replace('_5m.csv', '')
                data_dict[symbol_key] = df
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    
    return data_dict

def main():
    print("=" * 60)
    print("Backtesting Final Agent Strategy")
    print("=" * 60)
    print()
    
    # Load data (last 30 days)
    print("Loading 5-minute data (last 30 days)...")
    data_dict = load_5m_data(last_n_days=30)
    print(f"Loaded {len(data_dict)} symbols")
    
    # Show date range
    if data_dict:
        all_dates = []
        for df in data_dict.values():
            if len(df) > 0:
                all_dates.extend([df.index.min(), df.index.max()])
        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
            print(f"Date range: {min_date} to {max_date}")
    print()
    
    # Filter to allowed symbols from prompt
    allowed_symbols = [
        'DOGE', 'WIF', 'BRETT', 'TURBO', 'MEW', 'BAN', 'PNUT', 'POPCAT',
        'MOODENG', 'MEME', 'NEIRO', 'PEOPLE', 'BOME', 'DEGEN', 'GOAT',
        'BANANA', 'ACT', 'DOGS', 'CHILLGUY', 'HIPPO', '1000SHIB', '1000PEPE',
        '1000BONK', '1000FLOKI', '1000CHEEMS', '1000000MOG', '1000SATS',
        '1000CAT', '1MBABYDOGE', '1000WHY', 'KOMA'
    ]
    
    # Map symbols (remove /USDT:USDT suffix if present)
    filtered_data = {}
    for symbol, df in data_dict.items():
        base_symbol = symbol.replace('_USDT_USDT', '').replace('_USDT', '')
        if base_symbol in allowed_symbols or symbol in allowed_symbols:
            filtered_data[symbol] = df
    
    print(f"Filtered to {len(filtered_data)} allowed symbols")
    print()
    
    # Run backtest
    print("Running backtest...")
    results = backtest_strategy(filtered_data, initial_capital=10000.0, max_positions=4)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    # Print results
    print("=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Trades: {results['total_trades']}")
    print(f"Winning Trades: {results['winning_trades']}")
    print(f"Losing Trades: {results['losing_trades']}")
    print(f"Win Rate: {results['win_rate']:.2f}%")
    print(f"Total PnL: ${results['total_pnl']:.2f}")
    print(f"Final Capital: ${results['final_capital']:.2f}")
    print(f"Total Return: {results['total_return_pct']:.2f}%")
    print(f"Average Win: ${results['avg_win']:.2f}")
    print(f"Average Loss: ${results['avg_loss']:.2f}")
    print(f"Profit Factor: {results['profit_factor']:.2f}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    print()
    
    # Save detailed results
    output_file = f"research/BACKTEST_FINAL_AGENT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    os.makedirs('research', exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("# Final Agent Strategy Backtest Results\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Total Trades: {results['total_trades']}\n")
        f.write(f"- Win Rate: {results['win_rate']:.2f}%\n")
        f.write(f"- Total Return: {results['total_return_pct']:.2f}%\n")
        f.write(f"- Final Capital: ${results['final_capital']:.2f}\n")
        f.write(f"- Profit Factor: {results['profit_factor']:.2f}\n")
        f.write(f"- Sharpe Ratio: {results['sharpe_ratio']:.2f}\n")
        f.write(f"- Max Drawdown: {results['max_drawdown_pct']:.2f}%\n\n")
        f.write("## Trade Details\n\n")
        f.write("| Symbol | Entry Time | Exit Time | Side | Entry Price | Exit Price | PnL | Exit Reason | Leverage | Signal Strength | Duration (periods) |\n")
        f.write("|--------|------------|-----------|------|-------------|------------|-----|-------------|----------|-----------------|---------------------|\n")
        for trade in results['trades']:
            f.write(f"| {trade['symbol']} | {trade['entry_time']} | {trade['exit_time']} | {trade['side']} | "
                   f"${trade['entry_price']:.6f} | ${trade['exit_price']:.6f} | ${trade['pnl']:.2f} | "
                   f"{trade['exit_reason']} | {trade['leverage']}x | {trade['signal_strength']:.3f} | {trade.get('duration_periods', 0):.1f} |\n")
    
    print(f"Detailed results saved to: {output_file}")

if __name__ == '__main__':
    main()
