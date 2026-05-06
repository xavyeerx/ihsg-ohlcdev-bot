# ============================================
# TECHNICAL INDICATORS
# ============================================
# Matches Pine Script v5 logic

import pandas as pd
import numpy as np
from typing import Tuple, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import *


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()

def calculate_emas(df: pd.DataFrame) -> pd.DataFrame:
    df['ema20'] = calculate_ema(df['close'], EMA_FAST)
    df['ema50'] = calculate_ema(df['close'], EMA_MEDIUM)
    df['ema200']= calculate_ema(df['close'], EMA_SLOW)
    df['ma5']   = calculate_sma(df['close'], 5)
    df['ma10']  = calculate_sma(df['close'], 10)
    df['ma100'] = calculate_sma(df['close'], 100)
    df['ema_bullish_alignment'] = (df['ema20'] > df['ema50']) & (df['ema50'] > df['ema200'])
    df['ema_bearish_alignment'] = (df['ema20'] < df['ema50']) & (df['ema50'] < df['ema200'])
    df['price_above_ema20']  = df['close'] > df['ema20']
    df['price_above_ema50']  = df['close'] > df['ema50']
    df['price_above_ema200'] = df['close'] > df['ema200']
    return df

def calculate_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> pd.DataFrame:
    delta = df['close'].diff()
    gain  = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss))
    return df

def calculate_stochastic_rsi(df: pd.DataFrame) -> pd.DataFrame:
    if 'rsi' not in df.columns: calculate_rsi(df)
    lo = df['rsi'].rolling(window=STOCH_PERIOD).min()
    hi = df['rsi'].rolling(window=STOCH_PERIOD).max()
    raw = (100 * (df['rsi'] - lo) / (hi - lo)).fillna(50)
    df['stoch_k'] = raw.rolling(window=SMOOTH_K).mean()
    df['stoch_d'] = df['stoch_k'].rolling(window=SMOOTH_D).mean()
    df['stoch_overbought']  = df['stoch_k'] > STOCH_OVERBOUGHT
    df['stoch_oversold']    = df['stoch_k'] < STOCH_OVERSOLD
    df['stoch_k_cross_up']  = (df['stoch_k'] > df['stoch_d']) & (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1))
    df['stoch_k_cross_down']= (df['stoch_k'] < df['stoch_d']) & (df['stoch_k'].shift(1) >= df['stoch_d'].shift(1))
    return df

def calculate_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.DataFrame:
    tr1 = df['high'] - df['low']
    tr2 = abs(df['high'] - df['close'].shift(1))
    tr3 = abs(df['low']  - df['close'].shift(1))
    df['tr']  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(window=period).mean()
    df['atr_percent']       = (df['atr'] / df['close']) * 100
    df['is_volatile_enough']= df['atr_percent'] >= MIN_ATR_PERCENT
    return df

def calculate_adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.DataFrame:
    high_diff = df['high'].diff()
    low_diff  = -df['low'].diff()
    plus_dm   = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm  = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
    if 'atr' not in df.columns: calculate_atr(df, period)
    df['plus_di']  = 100 * (pd.Series(plus_dm,  index=df.index).rolling(window=period).mean() / df['atr'])
    df['minus_di'] = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=period).mean() / df['atr'])
    dx = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx']          = dx.rolling(window=period).mean()
    df['is_trending']  = df['adx'] > ADX_THRESHOLD
    df['is_sideways']  = df['adx'] <= ADX_THRESHOLD
    df['dmi_cross_up']   = (df['plus_di'] > df['minus_di'])  & (df['plus_di'].shift(1)  <= df['minus_di'].shift(1))
    df['dmi_cross_down'] = (df['plus_di'] < df['minus_di'])  & (df['plus_di'].shift(1)  >= df['minus_di'].shift(1))
    return df

def calculate_volume_analysis(df: pd.DataFrame) -> pd.DataFrame:
    df['avg_volume']        = df['volume'].rolling(window=VOLUME_PERIOD).mean()
    df['volume_ratio']      = df['volume'] / df['avg_volume']
    df['is_volume_spike']   = df['volume_ratio'] >= VOLUME_SPIKE_THRESHOLD
    df['is_unusual_volume'] = df['volume_ratio'] >= UNUSUAL_VOLUME_THRESHOLD
    df['is_high_volume']    = df['volume'] > MIN_VOLUME
    price_change = df['close'].diff()
    df['price_change']    = price_change
    df['volume_on_up']    = np.where(price_change > 0, df['volume'], 0)
    df['volume_on_down']  = np.where(price_change < 0, df['volume'], 0)
    df['avg_volume_up']   = pd.Series(df['volume_on_up'],   index=df.index).rolling(window=VOLUME_PERIOD).mean()
    df['avg_volume_down'] = pd.Series(df['volume_on_down'], index=df.index).rolling(window=VOLUME_PERIOD).mean()
    df['volume_bias_bullish'] = df['avg_volume_up'] > df['avg_volume_down']
    obv = np.where(df['close'] > df['close'].shift(1), df['volume'],
          np.where(df['close'] < df['close'].shift(1), -df['volume'], 0))
    df['obv']         = pd.Series(obv, index=df.index).cumsum()
    df['obv_ema']     = calculate_ema(df['obv'], 20)
    df['obv_bullish'] = df['obv'] > df['obv_ema']

    # Frequency Analyzer (jika kolom frequency tersedia dari OHLCV daily)
    if 'frequency' in df.columns:
        freq = pd.to_numeric(df['frequency'], errors='coerce').fillna(0)
        df['avg_frequency']      = freq.rolling(window=FREQUENCY_PERIOD).mean()
        df['frequency_ratio']    = np.where(df['avg_frequency'] > 0, freq / df['avg_frequency'], 1.0)
        df['is_frequency_spike'] = df['frequency_ratio'] >= FREQUENCY_SPIKE_THRESHOLD
        df['is_frequency_surge'] = df['frequency_ratio'] >= FREQUENCY_SURGE_THRESHOLD
        df['frequency_rising']   = freq > freq.shift(1)
    else:
        df['avg_frequency']      = np.nan
        df['frequency_ratio']    = 1.0
        df['is_frequency_spike'] = False
        df['is_frequency_surge'] = False
        df['frequency_rising']   = False

    # Alternative source: freq_analyzer value from API (sering lebih dekat ke panel chart)
    if 'freq_analyzer' in df.columns:
        fa = pd.to_numeric(df['freq_analyzer'], errors='coerce').fillna(0)
        df['avg_freq_analyzer'] = fa.rolling(window=FREQUENCY_PERIOD).mean()
        df['freq_analyzer_ratio'] = np.where(df['avg_freq_analyzer'] > 0, fa / df['avg_freq_analyzer'], 1.0)
        df['is_freq_analyzer_spike'] = df['freq_analyzer_ratio'] >= FREQ_ANALYZER_SPIKE_THRESHOLD
        df['is_freq_analyzer_surge'] = df['freq_analyzer_ratio'] >= FREQ_ANALYZER_SURGE_THRESHOLD
    else:
        df['avg_freq_analyzer'] = np.nan
        df['freq_analyzer_ratio'] = 1.0
        df['is_freq_analyzer_spike'] = False
        df['is_freq_analyzer_surge'] = False
    return df

def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    ema_fast = calculate_ema(df['close'], MACD_FAST)
    ema_slow = calculate_ema(df['close'], MACD_SLOW)
    df['macd_line']       = ema_fast - ema_slow
    df['macd_signal']     = calculate_ema(df['macd_line'], MACD_SIGNAL)
    df['macd_hist']       = df['macd_line'] - df['macd_signal']
    df['macd_bullish']    = df['macd_line'] > df['macd_signal']
    df['macd_bearish']    = df['macd_line'] < df['macd_signal']
    df['macd_cross_up']   = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
    df['macd_cross_down'] = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
    df['macd_hist_rising']= df['macd_hist'] > df['macd_hist'].shift(1)
    return df

def calculate_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    body       = abs(df['close'] - df['open'])
    upper_wick = df['high'] - df[['close','open']].max(axis=1)
    lower_wick = df[['close','open']].min(axis=1) - df['low']
    total_range= df['high'] - df['low']
    is_bull = df['close'] > df['open'];  is_bear = df['close'] < df['open']
    body1   = abs(df['close'].shift(1) - df['open'].shift(1))
    is_bull1= df['close'].shift(1) > df['open'].shift(1)
    is_bear1= df['close'].shift(1) < df['open'].shift(1)
    body2   = abs(df['close'].shift(2) - df['open'].shift(2))
    is_bull2= df['close'].shift(2) > df['open'].shift(2)
    is_bear2= df['close'].shift(2) < df['open'].shift(2)
    direction       = df['direction'] if 'direction' in df.columns else pd.Series(0, index=df.index)
    is_bullish_trend= direction == 1;  is_bearish_trend = direction == -1
    df['bullish_engulfing'] = (is_bear1 & is_bull & (df['close'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1)) & (body > body1))
    df['bearish_engulfing'] = (is_bull1 & is_bear & (df['close'] < df['open'].shift(1)) & (df['open'] > df['close'].shift(1)) & (body > body1))
    df['is_hammer']        = (lower_wick >= body*2) & (upper_wick < body*0.5) & (body > 0) & is_bearish_trend
    df['is_shooting_star'] = (upper_wick >= body*2) & (lower_wick < body*0.5) & (body > 0) & is_bullish_trend
    small_body1 = body1 < (total_range * 0.3)
    df['morning_star'] = (is_bear2 & (body2>0) & small_body1 & is_bull & (df['close'] > (df['open'].shift(2)+df['close'].shift(2))/2))
    df['evening_star'] = (is_bull2 & (body2>0) & small_body1 & is_bear & (df['close'] < (df['open'].shift(2)+df['close'].shift(2))/2))
    df['bullish_pattern'] = df['bullish_engulfing'] | df['is_hammer']        | df['morning_star']
    df['bearish_pattern'] = df['bearish_engulfing'] | df['is_shooting_star'] | df['evening_star']
    df['pattern_name'] = np.select(
        [df['bullish_engulfing'],df['is_hammer'],df['morning_star'],df['bearish_engulfing'],df['is_shooting_star'],df['evening_star']],
        ["ENGULF▲","HAMMER","M.STAR","ENGULF▼","S.STAR","E.STAR"], default="")
    return df

def _pivot_high_vectorized(high: pd.Series, lookback: int) -> pd.Series:
    highs = high.to_numpy(); n = len(highs); result = np.full(n, np.nan)
    for i in range(lookback, n-lookback):
        window = highs[i-lookback:i+lookback+1]
        if highs[i] == window.max(): result[i] = highs[i]
    return pd.Series(result, index=high.index)

def _pivot_low_vectorized(low: pd.Series, lookback: int) -> pd.Series:
    lows = low.to_numpy(); n = len(lows); result = np.full(n, np.nan)
    for i in range(lookback, n-lookback):
        window = lows[i-lookback:i+lookback+1]
        if lows[i] == window.min(): result[i] = lows[i]
    return pd.Series(result, index=low.index)

def calculate_support_resistance(df: pd.DataFrame, lookback: int = PIVOT_LOOKBACK) -> pd.DataFrame:
    df['pivot_high']      = _pivot_high_vectorized(df['high'], lookback)
    df['pivot_low']       = _pivot_low_vectorized(df['low'],  lookback)
    df['resistance']      = df['pivot_high'].ffill()
    df['support']         = df['pivot_low'].ffill()
    df['near_support']    = df['support'].notna()    & (df['close'] <= df['support']    * 1.02)
    df['near_resistance'] = df['resistance'].notna() & (df['close'] >= df['resistance'] * 0.98)
    return df

def _find_pivot_lows(df, lookback=DIV_PIVOT_LOOKBACK):
    return df['low'].rolling(window=lookback*2+1, center=True).apply(
        lambda x: x.iloc[lookback] if x.iloc[lookback]==x.min() else np.nan, raw=False)

def _find_pivot_highs(df, lookback=DIV_PIVOT_LOOKBACK):
    return df['high'].rolling(window=lookback*2+1, center=True).apply(
        lambda x: x.iloc[lookback] if x.iloc[lookback]==x.max() else np.nan, raw=False)

def calculate_divergence(df: pd.DataFrame) -> pd.DataFrame:
    if 'rsi' not in df.columns: calculate_rsi(df)
    n = len(df)
    bull_div = np.zeros(n, dtype=bool); bear_div = np.zeros(n, dtype=bool)
    div_strength = np.zeros(n, dtype=int)
    pivot_lows   = _find_pivot_lows(df);  pivot_highs = _find_pivot_highs(df)
    pli = pivot_lows.dropna().index.tolist(); phi = pivot_highs.dropna().index.tolist()
    has_stoch = 'stoch_k' in df.columns; has_macd = 'macd_hist_rising' in df.columns
    has_volume = 'volume' in df.columns; has_pattern = 'bullish_pattern' in df.columns
    has_obv = 'obv_bullish' in df.columns; has_support = 'near_support' in df.columns
    max_fresh = DIV_PIVOT_LOOKBACK + DIV_FRESHNESS_BARS
    best_bull = 0; found_bull = False
    for i in range(1, len(pli)):
        idx2=pli[i]; idx1=pli[i-1]
        pos2=df.index.get_loc(idx2); pos1=df.index.get_loc(idx1)
        sep=pos2-pos1
        if sep < DIV_MIN_SEPARATION or sep > DIV_MAX_SEPARATION: continue
        p1=df.loc[idx1,'low']; p2=df.loc[idx2,'low']
        r1=df.loc[idx1,'rsi']; r2=df.loc[idx2,'rsi']
        if pd.isna(r1) or pd.isna(r2): continue
        if p2 >= p1: continue
        if ((p1-p2)/p1)*100 < DIV_PRICE_MIN_DROP: continue
        if r2 <= r1+DIV_RSI_MIN_DIFF: continue
        if r1 >= DIV_RSI_OVERSOLD: continue
        if (n-1)-pos2 > max_fresh: continue
        if has_stoch and df.iloc[-1].get('stoch_k',50) > DIV_STOCH_MAX_K: continue
        v1=df.loc[idx1,'volume'] if has_volume else 0; v2=df.loc[idx2,'volume'] if has_volume else 0
        st=0
        if has_volume and v1>0 and v2<v1*0.85: st+=1
        if has_volume and v1>0 and v2<v1*0.6:  st+=1
        if has_pattern and df.loc[idx2,'bullish_pattern']: st+=1
        if has_macd and df.iloc[min(pos2+1,n-1)].get('macd_hist_rising',False): st+=1
        if has_obv and df.iloc[-1].get('obv_bullish',False): st+=1
        if has_support and df.loc[idx2,'near_support']: st+=1
        bull_div[pos2]=True; div_strength[pos2]=st
        if st>best_bull: best_bull=st
        found_bull=True
    if found_bull: bull_div[-1]=True; div_strength[-1]=best_bull
    found_bear=False
    for i in range(1, len(phi)):
        idx2=phi[i]; idx1=phi[i-1]
        pos2=df.index.get_loc(idx2); pos1=df.index.get_loc(idx1)
        sep=pos2-pos1
        if sep < DIV_MIN_SEPARATION or sep > DIV_MAX_SEPARATION: continue
        p1=df.loc[idx1,'high']; p2=df.loc[idx2,'high']
        r1=df.loc[idx1,'rsi'];  r2=df.loc[idx2,'rsi']
        if pd.isna(r1) or pd.isna(r2): continue
        if p2<=p1 or r2>=r1: continue
        if (n-1)-pos2 > max_fresh: continue
        bear_div[pos2]=True; found_bear=True
    if found_bear: bear_div[-1]=True
    df['bullish_divergence']=bull_div; df['bearish_divergence']=bear_div; df['div_strength']=div_strength
    return df

def calculate_targets(df: pd.DataFrame) -> pd.DataFrame:
    if 'atr' not in df.columns: calculate_atr(df)
    close=df['close']; atr=df['atr']
    df['tp1'] = close + (atr * TP1_MULTIPLIER)
    tp2_fallback  = close + (atr * TP2_MULTIPLIER)
    tp2_min_price = close + (atr * TP2_MIN_MULTIPLIER)
    tp2_max_price = close + (atr * TP2_MAX_MULTIPLIER)
    if 'resistance' in df.columns:
        res   = df['resistance']
        valid = res.notna() & (res>close) & (res>=tp2_min_price) & (res<=tp2_max_price)
        df['tp2']        = np.where(valid, res, tp2_fallback)
        df['tp2_source'] = np.where(valid, 'RESISTANCE', 'ATR')
    else:
        df['tp2']=tp2_fallback; df['tp2_source']='ATR'
    df['tp_swing']=df['tp2']
    return df

def calculate_momentum(df: pd.DataFrame, period: int = MOMENTUM_PERIOD) -> pd.DataFrame:
    df['roc'] = ((df['close'] - df['close'].shift(period)) / df['close'].shift(period)) * 100
    df['is_positive_momentum'] = df['roc'] > 0
    df['is_strong_momentum']   = abs(df['roc']) > 5
    return df

def calculate_dca_zones(df: pd.DataFrame) -> pd.DataFrame:
    df['swing_high']  = df['high'].rolling(window=DCA_LOOKBACK).max()
    df['swing_low']   = df['low'].rolling(window=DCA_LOOKBACK).min()
    df['swing_range'] = df['swing_high'] - df['swing_low']
    df['fib_618'] = df['swing_high'] - (df['swing_range'] * FIB_LEVEL_1/100)
    df['fib_850'] = df['swing_high'] - (df['swing_range'] * FIB_LEVEL_2/100)
    df['in_dca_zone1'] = (df['close'] <= df['fib_618']) & (df['close'] > df['fib_850'])
    df['in_dca_zone2'] = df['close'] <= df['fib_850']
    short_vol = df['volume'].rolling(window=5).mean()
    df['is_low_volume_correction'] = short_vol < (df['avg_volume'] * DCA_VOLUME_THRESHOLD)
    recent_down = pd.Series(df['volume_on_down']).rolling(window=5).mean()
    recent_up   = pd.Series(df['volume_on_up']).rolling(window=5).mean()
    df['is_distribution']       = recent_down > (recent_up * 1.5)
    df['is_healthy_correction'] = df['is_low_volume_correction'] & ~df['is_distribution']
    recent_high = df['high'].rolling(window=10).max()
    df['price_from_high'] = (recent_high - df['close']) / recent_high * 100
    df['is_in_correction']= df['price_from_high'] > 3
    df['ema20_touch'] = (df['low'] <= df['ema20']) & (df['close'] > df['ema20']*0.99) if 'ema20' in df.columns else False
    df['ema50_touch'] = (df['low'] <= df['ema50']) & (df['close'] > df['ema50']*0.99) if 'ema50' in df.columns else False
    return df

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    calculate_emas(df);  calculate_rsi(df);  calculate_stochastic_rsi(df)
    calculate_atr(df);   calculate_adx(df);  calculate_volume_analysis(df)
    calculate_macd(df);  calculate_momentum(df); calculate_dca_zones(df)
    calculate_candlestick_patterns(df); calculate_support_resistance(df)
    calculate_divergence(df)
    # De-fragment before final column inserts (targets) to avoid pandas PerformanceWarning.
    df = df.copy()
    calculate_targets(df)
    return df
