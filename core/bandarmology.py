# BANDARMOLOGY ANALYZER v2
#
# Komponen analisis:
#   A. Foreign Flow      : dari kolom foreignbuy/foreignsell (daily OHLCV)
#   B. Broker Local Flow : dari getBrokerTradeChart (top 5 broker net 7 hari)
#   C. Domestic Flow     : estimasi dari (value - foreign_value)
#   D. Frequency/Whale   : value/frequency → avg lot per transaksi
#   E. Volume Pattern    : spike, trend, absorbsi, baseline
#
# Skor max 30
#
# Broker chart:
#   - Top 5 broker net value per jam, 7 hari ke belakang
#   - dominant=BUYING → broker lokal mayoritas beli → konfirmasi akumulasi lokal
#   - dominant=SELLING → broker lokal mayoritas jual → tekanan distribusi

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

WINDOW_SHORT  = 5
WINDOW_MEDIUM = 20


@dataclass
class BandarmologyResult:
    symbol: str

    # Sinyal akumulasi / distribusi
    is_accumulating: bool  = False
    is_distributing: bool  = False
    accum_signal:    str   = "NEUTRAL"

    # Foreign flow
    foreign_dir:     str   = "NEUTRAL"
    foreign_net_buy: float = 0.0
    foreign_pct:     float = 0.0
    foreign_days:    int   = WINDOW_SHORT  # default window yang dipakai untuk foreign_net_buy

    # Broker lokal (dari broker_chart)
    broker_dominant: str   = "NEUTRAL"   # BUYING | SELLING | NEUTRAL (top 5 broker aktif, bukan hanya lokal)
    broker_net:      float = 0.0         # total net value 5 broker (Rp)
    broker_top_buyers:  list = field(default_factory=list)  # top 3 broker net beli [{code, net}, ...]
    broker_top_sellers: list = field(default_factory=list)  # top 3 broker net jual [{code, net}, ...]
    has_broker_data: bool  = False

    # Broker Summary (Ultra, 1D, per tanggal)
    has_broksum:       bool  = False
    broksum_date:      str   = ""        # YYYY-MM-DD (WIB)
    broksum_dominant:  str   = "NEUTRAL" # BUYING | SELLING | NEUTRAL
    broksum_total_net: float = 0.0
    broksum_top_buyers:  list = field(default_factory=list)  # [{code, net}, ...]
    broksum_top_sellers: list = field(default_factory=list)  # [{code, net}, ...]
    broksum_bandar:     str   = "NEUTRAL"  # BIG_ACC | BIG_DIST | NEUTRAL
    broksum_bandar_raw: str   = ""
    broksum_bandar_source: str = ""        # top1/top3/top5/top10/avg5/avg
    broksum_bandar_amount:  float = 0.0
    broksum_bandar_percent: float = 0.0
    broksum_bandar_total_value: float = 0.0
    broksum_total_buyer: int = 0
    broksum_total_seller: int = 0
    # Aliran non-retail (dari tipe investor per baris broksum: Asing, Pemerintah vs Lokal)
    broksum_non_retail_buy_pct: float = 0.0   # % nilai beli dari investor Asing+Pemerintah
    broksum_lokal_buy_pct:       float = 0.0   # % nilai beli sisi Lokal (campuran ritel/inst. domestik)
    broksum_non_retail_net:      float = 0.0   # net Rupiah non-retail (beli+jual, Asing+Pemerintah)

    # Domestic flow (estimasi)
    domestic_net:    float = 0.0
    domestic_dir:    str   = "NEUTRAL"

    # Frequency / whale
    avg_lot_size:    float = 0.0
    freq_ratio:      float = 0.0
    whale_signal:    bool  = False
    freq_signal:     str   = "NEUTRAL"

    # Volume pattern
    vol_ratio:       float = 0.0
    vol_trend:       str   = "FLAT"
    price_stability: float = 0.0
    absorption:      bool  = False

    # Score
    score:           int   = 0
    score_breakdown: Dict  = field(default_factory=dict)
    raw:             Dict  = field(default_factory=dict)


def _safe_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.zeros(len(df)), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def analyze_bandarmology(symbol: str, bundle: Dict[str, Any],
                          df: Optional[pd.DataFrame] = None,
                          broker_chart: Optional[Dict] = None) -> "BandarmologyResult":
    """
    Analisis bandarmology.

    Parameters:
        symbol       : kode saham
        bundle       : dict dari fetch_bandarmology_bundle
        df           : DataFrame OHLCV daily
        broker_chart : output dari parse_broker_chart() — opsional
    """
    result = BandarmologyResult(symbol=symbol, raw=bundle or {})

    if df is None or len(df) < WINDOW_SHORT:
        logger.debug(f"[{symbol}] Bandarmology: df kosong/pendek")
        return result

    volume       = _safe_series(df, "volume")
    close        = _safe_series(df, "close")
    high_col     = _safe_series(df, "high")
    low_col      = _safe_series(df, "low")
    value        = _safe_series(df, "value")
    foreign_buy  = _safe_series(df, "foreign_buy")
    foreign_sell = _safe_series(df, "foreign_sell")
    foreign_flow = _safe_series(df, "foreign_flow")
    frequency    = _safe_series(df, "frequency")

    w_s = WINDOW_SHORT
    w_m = min(WINDOW_MEDIUM, len(df))
    w_l = min(50, len(df))

    vol_short  = volume.iloc[-w_s:].mean()
    vol_medium = volume.iloc[-w_m:].mean()
    vol_long   = volume.iloc[-w_l:].mean()

    # ── A. FOREIGN FLOW (1D) ─────────────────────────────────────
    has_foreign = foreign_buy.sum() > 0 or foreign_sell.sum() > 0
    result.foreign_days = 1
    if has_foreign:
        fbuy_1d = float(foreign_buy.iloc[-1]) if len(foreign_buy) > 0 else 0.0
        fsell_1d = float(foreign_sell.iloc[-1]) if len(foreign_sell) > 0 else 0.0
        net_1d = fbuy_1d - fsell_1d
        result.foreign_net_buy = net_1d
        total_1d = fbuy_1d + fsell_1d
        result.foreign_pct = float(fbuy_1d / total_1d) if total_1d > 0 else 0.5
        if net_1d > 0:
            result.foreign_dir = "BUYING"
        elif net_1d < 0:
            result.foreign_dir = "SELLING"
    elif foreign_flow.sum() != 0:
        net_1d = float(foreign_flow.iloc[-1]) if len(foreign_flow) > 0 else 0.0
        result.foreign_net_buy = net_1d
        if net_1d > 0:
            result.foreign_dir = "BUYING"
        elif net_1d < 0:
            result.foreign_dir = "SELLING"
        has_foreign = True

    # ── B. BROKER LOCAL FLOW (dari broker_chart) ─────────────────
    broker_score = 0
    if broker_chart and isinstance(broker_chart, dict):
        result.has_broker_data  = True
        result.broker_dominant  = broker_chart.get("dominant", "NEUTRAL")
        result.broker_net       = float(broker_chart.get("total_net", 0))
        result.broker_top_buyers  = broker_chart.get("top_buyers",  [])
        result.broker_top_sellers = broker_chart.get("top_sellers", [])

        n_buy  = broker_chart.get("n_buy", 0)
        n_sell = broker_chart.get("n_sell", 0)
        total  = n_buy + n_sell

        if result.broker_dominant == "BUYING":
            # Mayoritas dari 5 broker net beli → akumulasi institusional lokal
            if n_buy >= 4:
                broker_score = 8   # 4-5 broker beli = sangat dominan
            elif n_buy == 3:
                broker_score = 5   # 3/5 broker beli = moderate
            else:
                broker_score = 2
        elif result.broker_dominant == "SELLING":
            if n_sell >= 4:
                broker_score = -6
            else:
                broker_score = -3
        # NEUTRAL: broker_score = 0

        logger.debug(f"[{symbol}] Broker: {result.broker_dominant} "
                     f"n_buy={n_buy} n_sell={n_sell} net={result.broker_net:.0f}")

    # ── C. DOMESTIC FLOW (estimasi) ──────────────────────────────
    domestic_score = 0
    if value.sum() > 0 and has_foreign:
        close_last      = float(close.iloc[-1]) if float(close.iloc[-1]) > 0 else 1.0
        foreign_val_buy  = float(foreign_buy.iloc[-1]) * close_last
        foreign_val_sell = float(foreign_sell.iloc[-1]) * close_last
        total_val_short  = float(value.iloc[-1]) if len(value) > 0 else 0.0
        result.domestic_net = float(total_val_short - (foreign_val_buy + foreign_val_sell))
        if result.domestic_net > 0 and result.foreign_dir == "SELLING":
            result.domestic_dir = "BUYING"
            domestic_score = 4

    # ── D. FREQUENCY / WHALE ─────────────────────────────────────
    freq_score     = 0
    freq_short_sum = frequency.iloc[-w_s:].sum()
    val_short_sum  = value.iloc[-w_s:].sum()
    if freq_short_sum > 0 and val_short_sum > 0:
        result.avg_lot_size  = float(val_short_sum / freq_short_sum)
        freq_long_sum        = frequency.iloc[-w_l:].sum()
        val_long_sum         = value.iloc[-w_l:].sum()
        avg_lot_baseline     = (val_long_sum / freq_long_sum) if freq_long_sum > 0 else 1.0
        lot_ratio            = result.avg_lot_size / avg_lot_baseline if avg_lot_baseline > 0 else 1.0
        result.freq_ratio    = float(lot_ratio)
        if lot_ratio > 2.0:
            result.whale_signal = True
            result.freq_signal  = "WHALE"
            freq_score          = 8
        elif lot_ratio > 1.5:
            result.freq_signal = "HIGH_LOT"
            freq_score         = 5
        elif lot_ratio > 1.2:
            result.freq_signal = "NORMAL"
            freq_score         = 2
        else:
            result.freq_signal = "RETAIL"

    # ── E. VOLUME PATTERN ─────────────────────────────────────────
    result.vol_ratio = float(vol_short / vol_medium) if vol_medium > 0 else 1.0
    result.vol_trend = "RISING" if (vol_short > vol_long and result.vol_ratio > 1.2) \
                       else ("FALLING" if vol_short < vol_long else "FLAT")

    vol_trend_score = 0
    if len(df) >= w_s * 2:
        vol_prev = volume.iloc[-(w_s*2):-w_s].mean()
        vol_curr = volume.iloc[-w_s:].mean()
        if vol_prev > 0 and vol_curr > vol_prev * 1.15:
            vol_trend_score = 5

    # Absorbsi: vol spike + harga stabil
    result.absorption = False
    absorption_score  = 0
    if len(df) >= w_m:
        close_short   = close.iloc[-w_s:]
        price_cv      = close_short.std() / close_short.mean() if close_short.mean() > 0 else 1.0
        result.price_stability = float(1 - min(price_cv * 10, 1.0))
        if result.vol_ratio > 1.3 and price_cv < 0.005:
            result.absorption = True; absorption_score = 8
        elif result.vol_ratio > 1.2 and price_cv < 0.01:
            result.absorption = True; absorption_score = 4

    vol_above_baseline = 4 if (vol_long > 0 and vol_short > vol_long * 1.1) else 0

    # ── F. PENALTI DISTRIBUSI ─────────────────────────────────────
    distrib_penalty = 0
    retail_penalty  = 0
    if result.vol_trend == "FALLING":
        close_now  = close.iloc[-w_s:].mean()
        close_prev = close.iloc[-w_m:-w_s].mean() if len(df) > w_s else close_now
        if close_prev > 0 and close_now < close_prev * 0.995:
            distrib_penalty        = -5
            result.is_distributing = True
            result.accum_signal    = "DISTRIBUTION"
    if vol_long > 0 and vol_short < vol_long * 0.5:
        retail_penalty = -2

    # ── G. OVERRIDE: Foreign + Broker Selling Dominant ───────────
    foreign_selling = (
        has_foreign and result.foreign_dir == "SELLING" and result.foreign_pct < 0.45
    )
    broker_selling = result.has_broker_data and result.broker_dominant == "SELLING"

    # Distribusi jika foreign DAN broker keduanya jual
    if (foreign_selling or broker_selling) and not result.is_distributing:
        if foreign_selling and broker_selling:
            # Dua konfirmasi distribusi → kuat
            result.is_distributing = True
            result.is_accumulating = False
            result.accum_signal    = "DISTRIBUTION"
        elif foreign_selling:
            result.is_distributing = True
            result.is_accumulating = False
            result.accum_signal    = "DISTRIBUTION"
        # broker_selling saja tanpa foreign → tidak langsung DISTRIBUTION,
        # bisa jadi profit-taking institusi lokal sementara asing masih beli

    # ── H. SINYAL AKUMULASI ───────────────────────────────────────
    if not result.is_distributing:
        absorb_ok       = result.absorption
        vol_rising_ok   = vol_trend_score > 0
        foreign_buy_ok  = result.foreign_dir == "BUYING"
        whale_ok        = result.whale_signal or result.freq_signal == "HIGH_LOT"
        domestic_buy    = result.domestic_dir == "BUYING"
        broker_buy_ok   = result.has_broker_data and result.broker_dominant == "BUYING"

        # STRONG: kombinasi 2+ sinyal beli
        strong_signals = sum([
            absorb_ok and vol_rising_ok,
            foreign_buy_ok and vol_rising_ok,
            broker_buy_ok and (whale_ok or vol_rising_ok),
            broker_buy_ok and foreign_buy_ok,
        ])
        if strong_signals >= 1 or (broker_buy_ok and whale_ok and vol_rising_ok):
            result.is_accumulating = True
            result.accum_signal    = "STRONG_ACCUMULATION"
        elif absorb_ok or (foreign_buy_ok and (whale_ok or vol_rising_ok)) \
                or broker_buy_ok or (domestic_buy and whale_ok):
            result.is_accumulating = True
            result.accum_signal    = "ACCUMULATION"
        elif foreign_buy_ok:
            result.is_accumulating = True
            result.accum_signal    = "ACCUMULATION"
        else:
            result.accum_signal = "NEUTRAL"

    # ── I. SCORING ────────────────────────────────────────────────
    score = 0
    bd    = {}

    if result.vol_ratio > 1.5:
        score += 6;  bd["vol_spike"] = 6
    elif result.vol_ratio > 1.2:
        score += 3;  bd["vol_spike"] = 3
    else:
        bd["vol_spike"] = 0

    score += vol_trend_score;   bd["vol_trend"]    = vol_trend_score
    score += absorption_score;  bd["absorption"]   = absorption_score
    score += vol_above_baseline; bd["vol_baseline"] = vol_above_baseline
    score += freq_score;        bd["freq_whale"]   = freq_score
    score += domestic_score;    bd["domestic"]     = domestic_score
    score += broker_score;      bd["broker_local"] = broker_score

    foreign_score = 0
    if has_foreign:
        if result.foreign_dir == "BUYING":
            if result.foreign_pct > 0.65:   foreign_score = 6
            elif result.foreign_pct > 0.55: foreign_score = 4
            else:                           foreign_score = 2
        elif result.foreign_dir == "SELLING":
            foreign_score = -8 if result.foreign_pct < 0.35 else -4
    score += foreign_score; bd["foreign_flow"] = foreign_score

    score += distrib_penalty; bd["distrib_penalty"] = distrib_penalty
    score += retail_penalty;  bd["retail_penalty"]  = retail_penalty

    result.score           = max(0, min(30, score))
    result.score_breakdown = bd

    logger.debug(
        f"[{symbol}] Bandro={result.score}/30 | {result.accum_signal} | "
        f"broker={result.broker_dominant} foreign={result.foreign_dir} "
        f"whale={result.whale_signal} vol={result.vol_ratio:.2f}"
    )
    return result
