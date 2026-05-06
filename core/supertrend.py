# ============================================
# SUPERTREND CALCULATION
# ============================================
# Matches Pine Script v3 logic exactly

import pandas as pd
import numpy as np


def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    df = df.copy()
    original_index = df.index
    df = df.reset_index(drop=True)

    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift(1))
    df['tr3'] = abs(df['low'] - df['close'].shift(1))
    df['tr']  = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=period).mean()

    hl2         = (df['high'] + df['low']) / 2
    basic_upper = (hl2 + (multiplier * df['atr'])).values
    basic_lower = (hl2 - (multiplier * df['atr'])).values

    n          = len(df)
    upper_band = basic_upper.copy()
    lower_band = basic_lower.copy()
    direction  = np.ones(n, dtype=int)
    close      = df['close'].values

    for i in range(1, n):
        if pd.isna(basic_upper[i]) or pd.isna(upper_band[i-1]):
            continue
        upper_band[i] = basic_upper[i] if (basic_upper[i] < upper_band[i-1] or close[i-1] > upper_band[i-1]) else upper_band[i-1]
        lower_band[i] = basic_lower[i] if (basic_lower[i] > lower_band[i-1] or close[i-1] < lower_band[i-1]) else lower_band[i-1]
        if direction[i-1] == -1:
            direction[i] = 1  if close[i] > upper_band[i-1] else -1
        else:
            direction[i] = -1 if close[i] < lower_band[i-1] else 1

    df['upper_band'] = upper_band
    df['lower_band'] = lower_band
    df['direction']  = direction
    df['supertrend'] = np.where(direction == 1, lower_band, upper_band)

    supertrend     = df['supertrend'].values
    prev_close     = np.roll(close, 1)
    prev_supertrend= np.roll(supertrend, 1)

    df['bullish_break'] = (prev_close <= prev_supertrend) & (close > supertrend)
    df['bearish_break'] = (prev_close >= prev_supertrend) & (close < supertrend)
    df.loc[0, 'bullish_break'] = False
    df.loc[0, 'bearish_break'] = False
    df['supertrend_changed'] = df['direction'] != df['direction'].shift(1)
    df = df.drop(columns=['tr1', 'tr2', 'tr3', 'tr'], errors='ignore')
    df.index = original_index
    return df


def is_bullish(df):       return len(df) > 0 and df['direction'].iloc[-1] == 1
def is_bearish(df):       return len(df) == 0 or df['direction'].iloc[-1] == -1
def get_supertrend_value(df): return df['supertrend'].iloc[-1] if len(df) > 0 else 0.0
def just_turned_bullish(df):  return len(df) >= 2 and bool(df['bullish_break'].iloc[-1])
def just_turned_bearish(df):  return len(df) >= 2 and bool(df['bearish_break'].iloc[-1])
