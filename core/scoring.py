# ============================================================
# SCORING — pure teknikal, maks 100
# Disesuaikan dengan bot lama ihsg-supertrend-scanner v5
# ============================================================
import pandas as pd
from typing import Dict
from dataclasses import dataclass, field

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import STRONG_BUY_THRESHOLD, ACCUMULATE_THRESHOLD, HOLD_THRESHOLD
from core.bandarmology import BandarmologyResult


@dataclass
class ScoreResult:
    symbol:           str
    total_score:      int
    status:           str
    status_emoji:     str
    trend_score:      float = 0.0
    regime_score:     float = 0.0
    volume_score:     float = 0.0
    momentum_score:   float = 0.0
    position_score:   float = 0.0
    pattern_score:    float = 0.0
    technical_total:  float = 0.0
    bandro_score:     int   = 0
    bandro_breakdown: Dict  = field(default_factory=dict)
    is_trending:      bool  = False
    supertrend_bullish: bool = False
    just_broke_up:    bool  = False


def _trend_score(row):
    # Sama dengan bot lama v5:
    # supertrend bullish +10, EMA bullish alignment +10, trend aligned +5 = max 25
    s = 0.0
    if row.get("direction", -1) == 1:    s += 10.0  # supertrend bullish
    if row.get("ema_bullish_alignment"): s += 10.0  # EMA 20>50>200
    if row.get("direction", -1) == 1:    s +=  5.0  # trend aligned (daily TF)
    return min(s, 25.0)

def _regime_score(row):
    # max 12 pts
    s = 0.0
    if row.get("is_trending"):        s += 8.0
    if row.get("is_volatile_enough"): s += 4.0
    return min(s, 12.0)

def _volume_score(row):
    # max 18 pts -- unusual OR spike (tidak double counting), sama dengan v5
    s = 0.0
    if row.get("is_high_volume"):    s += 4.0
    if row.get("is_unusual_volume"): s += 10.0
    elif row.get("is_volume_spike"): s += 7.0
    if row.get("obv_bullish") and row.get("direction", -1) == 1: s += 4.0
    return min(s, 18.0)

def _momentum_score(row):
    # max 25 pts
    s = 0.0
    if row.get("is_positive_momentum"): s += 8.0
    if row.get("is_strong_momentum") and row.get("is_positive_momentum"): s += 4.0
    if row.get("stoch_oversold") and row.get("direction", -1) == 1: s += 8.0
    if row.get("macd_bullish"): s += 5.0
    return min(s, 25.0)

def _position_score(row):
    # max 15 pts
    s = 0.0
    if row.get("price_above_ema200"): s += 6.0
    if row.get("price_above_ema50"):  s += 5.0
    if row.get("price_above_ema20"):  s += 4.0
    return min(s, 15.0)

def _pattern_score(row):
    # max 5 pts
    s = 0.0
    if row.get("bullish_pattern"): s += 3.0
    if row.get("bullish_divergence"):
        strength = row.get("div_strength", 0)
        s += 4.0 if strength >= 3 else (2.0 if strength >= 1 else 1.0)
    return min(s, 5.0)


def calculate_technical_score(df: pd.DataFrame) -> Dict[str, float]:
    if len(df) == 0:
        return {k: 0.0 for k in ("trend","regime","volume","momentum","position","pattern","total")}

    row      = df.iloc[-1]
    trend    = _trend_score(row)
    regime   = _regime_score(row)
    vol      = _volume_score(row)
    momentum = _momentum_score(row)
    pos      = _position_score(row)
    pattern  = _pattern_score(row)
    total    = trend + regime + vol + momentum + pos + pattern

    # Sideways penalty (v5): score * 0.7
    if row.get("is_sideways", True) and not row.get("is_unusual_volume"):
        total *= 0.7

    # Bearish divergence penalty (v5): score * 0.9
    if row.get("bearish_divergence") and row.get("direction", -1) == 1:
        total *= 0.9

    return {
        "trend": trend, "regime": regime, "volume": vol,
        "momentum": momentum, "position": pos, "pattern": pattern,
        "total": min(total, 100.0),
    }


def calculate_score(symbol: str, df: pd.DataFrame, bandro: BandarmologyResult = None) -> ScoreResult:
    tech  = calculate_technical_score(df)
    total = max(0, min(100, int(round(tech["total"]))))

    row             = df.iloc[-1] if len(df) > 0 else pd.Series(dtype=object)
    is_trending     = bool(row.get("is_trending", False))
    supertrend_bull = bool(row.get("direction", -1) == 1)
    just_broke_up   = bool(row.get("bullish_break", False))

    # STRONG BUY: total >= 70 AND is_trending (ADX > ADX_THRESHOLD)
    if total >= STRONG_BUY_THRESHOLD and is_trending:
        status, emoji = "STRONG BUY", "🟢"
    elif total >= ACCUMULATE_THRESHOLD:
        status, emoji = "ACCUMULATE", "🔵"
    elif total >= HOLD_THRESHOLD:
        status, emoji = "HOLD", "🟡"
    else:
        status, emoji = "AVOID", "🔴"

    return ScoreResult(
        symbol=symbol, total_score=total, status=status, status_emoji=emoji,
        trend_score=tech["trend"], regime_score=tech["regime"],
        volume_score=tech["volume"], momentum_score=tech["momentum"],
        position_score=tech["position"], pattern_score=tech["pattern"],
        technical_total=tech["total"],
        bandro_score=0,
        bandro_breakdown={},
        is_trending=is_trending, supertrend_bullish=supertrend_bull,
        just_broke_up=just_broke_up,
    )
