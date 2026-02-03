#!/usr/bin/env python3
"""
Grid search optimization for Final Agent Strategy (5m, 30-day data).
No new indicators; only thresholds and ATR exits are tuned.
"""

import glob
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import datetime

import numpy as np
import pandas as pd


@dataclass
class StrategyConfig:
    volume_ratio_threshold: float
    trend_strength_threshold: float
    signal_threshold: float
    stop_loss_atr: float
    take_profit_atr: float


class FinalAgentStrategyParam:
    """Parameterized version of FinalAgentStrategy for grid search."""

    def __init__(self, config: StrategyConfig):
        self.config = config

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
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

        return df

    def calculate_signal_strength(self, row: pd.Series, side: str) -> float:
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

        signal = 0.35 * mom_str + 0.25 * vol_str + 0.25 * trend_str + 0.15 * rsi_str
        return signal

    def get_leverage(self, signal_strength: float) -> float:
        if signal_strength >= 0.75:
            return 20.0
        elif signal_strength >= 0.60:
            return 15.0
        elif signal_strength >= 0.45:
            return 10.0
        return 0.0

    def check_long_entry(self, row: pd.Series) -> Tuple[bool, float]:
        required_cols = ['ema12_5m', 'ema36_5m', 'mom12_5m', 'rsi14_5m', 'volume_ratio',
                        'macd_5m', 'trend_strength', 'atr14_5m']
        if any(pd.isna(row[col]) for col in required_cols):
            return False, 0.0

        if not (row['ema12_5m'] > row['ema36_5m']):
            return False, 0.0

        if not (row['mom12_5m'] > 0.005):
            return False, 0.0

        if not (row['rsi14_5m'] > 52 and row['rsi14_5m'] < 60):
            return False, 0.0

        if not (row['volume_ratio'] > self.config.volume_ratio_threshold):
            return False, 0.0

        if not (row['trend_strength'] > self.config.trend_strength_threshold and
                row['volume_ratio'] > self.config.volume_ratio_threshold and
                row['macd_5m'] > 0):
            return False, 0.0

        if not (abs(row['mom12_5m']) > 0.003):
            return False, 0.0

        signal_strength = self.calculate_signal_strength(row, 'LONG')
        if signal_strength <= self.config.signal_threshold:
            return False, 0.0

        return True, signal_strength

    def check_short_entry(self, row: pd.Series) -> Tuple[bool, float]:
        required_cols = ['ema12_5m', 'ema36_5m', 'mom12_5m', 'rsi14_5m', 'volume_ratio',
                        'macd_5m', 'trend_strength', 'atr14_5m']
        if any(pd.isna(row[col]) for col in required_cols):
            return False, 0.0

        if not (row['ema12_5m'] < row['ema36_5m']):
            return False, 0.0

        if not (row['mom12_5m'] < -0.005):
            return False, 0.0

        if not (row['rsi14_5m'] < 48 and row['rsi14_5m'] > 40):
            return False, 0.0

        if not (row['volume_ratio'] > self.config.volume_ratio_threshold):
            return False, 0.0

        if not (row['trend_strength'] > self.config.trend_strength_threshold and
                row['volume_ratio'] > self.config.volume_ratio_threshold and
                row['macd_5m'] < 0):
            return False, 0.0

        if not (abs(row['mom12_5m']) > 0.003):
            return False, 0.0

        signal_strength = self.calculate_signal_strength(row, 'SHORT')
        if signal_strength <= self.config.signal_threshold:
            return False, 0.0

        return True, signal_strength


def load_5m_data(last_n_days: int = 30) -> Dict[str, pd.DataFrame]:
    data_dict = {}
    csv_files = glob.glob('data/*_5m.csv')
    cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=last_n_days)

    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            df = df[df.index >= cutoff_date]
            if len(df) >= 100:
                symbol_key = os.path.basename(filepath).replace('_5m.csv', '')
                data_dict[symbol_key] = df
        except Exception:
            pass

    return data_dict


def backtest_strategy(data_dict: Dict[str, pd.DataFrame], config: StrategyConfig,
                     initial_capital: float = 10000.0, max_positions: int = 4,
                     fee_rate: float = 0.0001) -> Dict:
    strategy = FinalAgentStrategyParam(config)
    capital = initial_capital
    positions = {}
    all_trades = []

    # Precompute indicators per symbol
    indicators = {}
    for symbol, data in data_dict.items():
        indicators[symbol] = strategy.calculate_indicators(data)

    for symbol, df in indicators.items():
        if len(df) < 100:
            continue

        for idx, row in df.iterrows():
            # Update existing positions
            if symbol in positions:
                position = positions[symbol]

                # Update highest/lowest price for trailing stop
                if position['side'] == 'LONG':
                    position['highest_price'] = max(position['highest_price'], row['close'])
                else:
                    position['lowest_price'] = min(position['lowest_price'], row['close'])

                # Check exit
                current_price = row['close']
                periods_held = (idx - position['entry_time']).total_seconds() / 300

                # Max hold
                if periods_held >= 72:
                    exit_reason = 'MAX_HOLD'
                else:
                    exit_reason = None

                # Stop Loss
                if exit_reason is None:
                    if position['side'] == 'LONG':
                        if current_price <= position['entry_price'] - (config.stop_loss_atr * position['atr']):
                            exit_reason = 'STOP_LOSS'
                    else:
                        if current_price >= position['entry_price'] + (config.stop_loss_atr * position['atr']):
                            exit_reason = 'STOP_LOSS'

                # Take Profit
                if exit_reason is None:
                    if position['side'] == 'LONG':
                        if current_price >= position['entry_price'] + (config.take_profit_atr * position['atr']):
                            exit_reason = 'TAKE_PROFIT'
                    else:
                        if current_price <= position['entry_price'] - (config.take_profit_atr * position['atr']):
                            exit_reason = 'TAKE_PROFIT'

                # Trailing Stop (after 1.0×ATR profit)
                if exit_reason is None:
                    if position['side'] == 'LONG':
                        profit = current_price - position['entry_price']
                        if profit >= 1.0 * position['atr']:
                            trailing_stop = position['highest_price'] - (1.0 * position['atr'])
                            if current_price <= trailing_stop:
                                exit_reason = 'TRAILING_STOP'
                    else:
                        profit = position['entry_price'] - current_price
                        if profit >= 1.0 * position['atr']:
                            trailing_stop = position['lowest_price'] + (1.0 * position['atr'])
                            if current_price >= trailing_stop:
                                exit_reason = 'TRAILING_STOP'

                # Trend Reversal (6-period min, 2-period persistence)
                if exit_reason is None:
                    if periods_held >= 6:
                        if position['side'] == 'LONG':
                            if row['ema12_5m'] < row['ema36_5m'] and row['macd_5m'] < 0:
                                position['trend_reversal_count'] += 1
                                if position['trend_reversal_count'] >= 2:
                                    exit_reason = 'TREND_REVERSAL'
                            else:
                                position['trend_reversal_count'] = 0
                        else:
                            if row['ema12_5m'] > row['ema36_5m'] and row['macd_5m'] > 0:
                                position['trend_reversal_count'] += 1
                                if position['trend_reversal_count'] >= 2:
                                    exit_reason = 'TREND_REVERSAL'
                            else:
                                position['trend_reversal_count'] = 0
                    else:
                        position['trend_reversal_count'] = 0

                if exit_reason:
                    exit_price = current_price
                    notional = position['size'] * position['entry_price']
                    entry_fee = notional * fee_rate
                    exit_fee = position['size'] * exit_price * fee_rate
                    if position['side'] == 'LONG':
                        price_change_pct = (exit_price - position['entry_price']) / position['entry_price']
                    else:
                        price_change_pct = (position['entry_price'] - exit_price) / position['entry_price']
                    margin = notional / position['leverage']
                    pnl = margin * price_change_pct * position['leverage'] - entry_fee - exit_fee

                    capital += margin + pnl
                    all_trades.append({
                        'symbol': symbol,
                        'pnl': pnl,
                        'exit_reason': exit_reason
                    })
                    del positions[symbol]

            # Entries
            if len(positions) < max_positions and symbol not in positions:
                can_long, signal_strength_long = strategy.check_long_entry(row)
                if can_long:
                    leverage = strategy.get_leverage(signal_strength_long)
                    if leverage <= 0:
                        continue
                    position_size_pct = 0.20 * signal_strength_long
                    notional = capital * position_size_pct * leverage
                    size = notional / row['close']
                    margin = notional / leverage
                    if margin <= capital * 0.9:
                        positions[symbol] = {
                            'side': 'LONG',
                            'entry_price': row['close'],
                            'entry_time': idx,
                            'size': size,
                            'leverage': leverage,
                            'atr': row['atr14_5m'],
                            'highest_price': row['close'],
                            'lowest_price': row['close'],
                            'trend_reversal_count': 0,
                        }
                        capital -= margin
                    continue

                can_short, signal_strength_short = strategy.check_short_entry(row)
                if can_short:
                    leverage = strategy.get_leverage(signal_strength_short)
                    if leverage <= 0:
                        continue
                    position_size_pct = 0.20 * signal_strength_short
                    notional = capital * position_size_pct * leverage
                    size = notional / row['close']
                    margin = notional / leverage
                    if margin <= capital * 0.9:
                        positions[symbol] = {
                            'side': 'SHORT',
                            'entry_price': row['close'],
                            'entry_time': idx,
                            'size': size,
                            'leverage': leverage,
                            'atr': row['atr14_5m'],
                            'highest_price': row['close'],
                            'lowest_price': row['close'],
                            'trend_reversal_count': 0,
                        }
                        capital -= margin

    if not all_trades:
        return {'error': 'No trades'}

    trades_df = pd.DataFrame(all_trades)
    total_pnl = trades_df['pnl'].sum()
    total_return = ((capital - initial_capital) / initial_capital) * 100
    win_rate = (trades_df['pnl'] > 0).mean() * 100
    avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean()
    avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean()
    profit_factor = abs(avg_win / avg_loss) if avg_loss else 0

    return {
        'total_trades': len(trades_df),
        'win_rate': win_rate,
        'total_return_pct': total_return,
        'profit_factor': profit_factor,
    }


def main():
    print("Loading 30-day 5m data...")
    data = load_5m_data(last_n_days=30)
    print(f"Loaded {len(data)} symbols")

    # Grid: keep small for speed
    volume_thresholds = [1.08, 1.10, 1.12]
    trend_thresholds = [0.0012, 0.0015]
    signal_thresholds = [0.45]
    sl_mults = [2.0, 2.5]
    tp_mults = [2.5, 3.0]

    results = []

    total_runs = len(volume_thresholds) * len(trend_thresholds) * len(signal_thresholds) * len(sl_mults) * len(tp_mults)
    run_idx = 0

    for vol in volume_thresholds:
        for trend in trend_thresholds:
            for signal in signal_thresholds:
                for sl in sl_mults:
                    for tp in tp_mults:
                        if tp <= sl:
                            continue
                        run_idx += 1
                        print(f"Running {run_idx}/{total_runs}: vol={vol}, trend={trend}, signal={signal}, SL={sl}, TP={tp}")
                        config = StrategyConfig(
                            volume_ratio_threshold=vol,
                            trend_strength_threshold=trend,
                            signal_threshold=signal,
                            stop_loss_atr=sl,
                            take_profit_atr=tp,
                        )
                        res = backtest_strategy(data, config)
                        if 'error' in res:
                            continue
                        results.append({
                            **res,
                            'volume_ratio_threshold': vol,
                            'trend_strength_threshold': trend,
                            'signal_threshold': signal,
                            'stop_loss_atr': sl,
                            'take_profit_atr': tp,
                        })

    if not results:
        print("No results")
        return

    df = pd.DataFrame(results)

    # Composite score: prioritize return, then win rate, then trades
    df['score'] = df['total_return_pct'] + (df['win_rate'] * 0.5) + (df['total_trades'] / 100)
    df = df.sort_values(by='score', ascending=False)

    print("\nTop 10 configs by score:")
    print(df.head(10).to_string(index=False))

    # Save full results
    output = Path('research/OPTIMIZATION_GRID_RESULTS.csv')
    df.to_csv(output, index=False)
    print(f"\nFull grid saved to: {output}")


if __name__ == '__main__':
    main()
