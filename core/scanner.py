# SCANNER -- Orchestrator per saham (v2 — signal-based like ihsg-supertrend-scanner)
import logging, time
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.settings   import (
    RATE_LIMIT_DELAY, OHLCV_INTERVAL, OHLCV_BARS,
    NOON_OHLCV_INTERVAL, NOON_OHLCV_BARS, NOON_DAILY_BARS,
    STRONG_BUY_THRESHOLD, ACCUMULATE_THRESHOLD,
    CONFIRMATION_BARS, MIN_DAILY_TURNOVER,
    EMA_FAST, EMA_MEDIUM,
    FREQUENCY_SPIKE_THRESHOLD,
    FREQ_ANALYZER_SPIKE_THRESHOLD,
    FA_MIN_STRENGTH, FA_MIN_FLOW_SCORE,
    INTRADAY_NOON_MIN_SCORE, INTRADAY_NOON_MIN_UPSIDE_PCT,
    INTRADAY_NOON_MAX_RUNUP_PCT,
    INTRADAY_NOON_REQUIRE_DAILY_BIAS,
    INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA50,
    INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA20,
    NON_RETAIL_FLOW_MIN_PCT,
)
from core.data_fetcher import (
    fetch_ohlcv, fetch_bandarmology_bundle,
)
from core.supertrend   import calculate_supertrend, just_turned_bullish
from core.indicators   import calculate_all_indicators, calculate_ema
from core.bandarmology import analyze_bandarmology, BandarmologyResult
from core.scoring      import calculate_score, ScoreResult

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    symbol:         str
    score_result:   Optional[ScoreResult]        = None
    bandro:         Optional[BandarmologyResult] = None
    current_price:  float = 0.0
    change_pct:     float = 0.0
    tp1:            float = 0.0
    tp2:            float = 0.0
    tp2_source:     str   = "ATR"
    supertrend_val: float = 0.0
    support:        float = 0.0
    resistance:     float = 0.0
    volume_ratio:   float = 0.0
    adx:            float = 0.0
    macd_status:    str   = ""
    obv_status:     str   = ""
    div_strength:   int   = 0
    div_grade:      str   = ""
    correction_pct: float = 0.0
    early_strength: int   = 0
    frequency_ratio:float = 1.0
    frequency_strength:int = 0
    frequency_curr: float = 0.0
    frequency_avg:  float = 0.0
    frequency_recent_max: float = 1.0
    frequency_recent_spike_count: int = 0
    frequency_stealth_volume_ok: bool = False
    flow_score: int = 0
    flow_stage: str = ""
    avg_turnover:   float = 0.0
    error:          Optional[str] = None
    # DataFrame OHLCV — untuk analisis lanjutan / debug (tidak dikirim ke Telegram)
    df:             Any = field(default=None, repr=False, compare=False)

    # ── Signal flags (sama dengan bot lama) ──────────────────
    is_strong_buy:  bool = False   # Supertrend breakout confirmed + score >= 70
    is_accumulation:bool = False   # Bullish + stoch oversold + volume spike
    is_bull_div:    bool = False   # Bullish divergence (bearish trend)
    is_early_entry: bool = False   # Serok bawah / healthy correction
    is_frequency_analyzer: bool = False  # Lonjakan frequency (early bandar accumulation)


def scan_symbol(symbol: str, prev_states: Dict = None, session: str = "") -> ScanResult:
    result = ScanResult(symbol=symbol)

    sess = (session or "").strip().lower()
    is_noon = sess == "noon"

    daily_df = None
    if is_noon:
        # Likuiditas + bias harian + bandarmology (asing/freq) tetap dari daily.
        daily_df = fetch_ohlcv(symbol, interval="daily", limit=NOON_DAILY_BARS)
        if daily_df is None or len(daily_df) < 50:
            result.error = "Data OHLCV harian tidak cukup"
            return result

        if "close" in daily_df.columns and "volume" in daily_df.columns:
            dfc = daily_df.copy()
            dfc["turnover"] = dfc["close"] * dfc["volume"]
            result.avg_turnover = float(dfc["turnover"].rolling(5).mean().iloc[-1])

        if INTRADAY_NOON_REQUIRE_DAILY_BIAS:
            close_d = pd.to_numeric(daily_df["close"], errors="coerce")
            ema20_d = calculate_ema(close_d, EMA_FAST)
            ema50_d = calculate_ema(close_d, EMA_MEDIUM)
            last_c = float(close_d.iloc[-1])
            e20 = float(ema20_d.iloc[-1])
            e50 = float(ema50_d.iloc[-1])
            bias_ok = True
            if INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA50:
                bias_ok = bias_ok and last_c >= e50
            if INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA20:
                bias_ok = bias_ok and last_c >= e20
            if not bias_ok:
                result.error = "Daily bias tidak mendukung (di bawah EMA20/50)"
                return result

        df = fetch_ohlcv(symbol, interval=NOON_OHLCV_INTERVAL, limit=NOON_OHLCV_BARS)
        if df is None or len(df) < 50:
            result.error = "Data OHLCV intraday tidak cukup"
            return result
        bandro_df = daily_df
    else:
        df = fetch_ohlcv(symbol, interval=OHLCV_INTERVAL, limit=OHLCV_BARS)
        if df is None or len(df) < 50:
            result.error = "Data OHLCV tidak cukup"
            return result
        bandro_df = df

    # 2. Hitung indikator teknikal
    try:
        df = calculate_supertrend(df)
        df = calculate_all_indicators(df)
    except Exception as e:
        result.error = f"Error indikator: {e}"
        logger.error(f"[{symbol}] {result.error}")
        return result

    last = df.iloc[-1]
    result.df = df  # simpan untuk SM Engine (Pass-1 tidak perlu re-fetch)

    # ── Info dasar ──────────────────────────────────────────
    result.current_price  = float(last.get("close", 0))
    result.supertrend_val = float(last.get("supertrend", 0))
    result.tp1            = float(last.get("tp1", 0))
    result.tp2            = float(last.get("tp2", 0))
    result.tp2_source     = str(last.get("tp2_source", "ATR"))
    result.support        = float(last.get("support", 0))
    result.resistance     = float(last.get("resistance", 0))
    result.volume_ratio   = float(last.get("volume_ratio", 1.0))
    result.adx            = float(last.get("adx", 0.0))

    # Turnover harian (untuk filter likuiditas)
    if not is_noon:
        if "close" in df.columns and "volume" in df.columns:
            # Avoid fragmented-frame warning when adding new derived columns.
            df = df.copy()
            df["turnover"] = df["close"] * df["volume"]
            result.avg_turnover = float(df["turnover"].rolling(5).mean().iloc[-1])

    if len(df) >= 2:
        prev = float(df.iloc[-2].get("close", result.current_price))
        if prev > 0:
            result.change_pct = ((result.current_price - prev) / prev) * 100
    high_px = float(last.get("high", 0.0) or 0.0)
    close_px = float(last.get("close", 0.0) or 0.0)
    open_px = float(last.get("open", close_px) or close_px)
    volume_ratio_now = float(last.get("volume_ratio", 1.0) or 1.0)
    upper_wick_ratio = ((high_px - max(close_px, open_px)) / high_px) if high_px > 0 else 0.0
    # No distribution candle:
    # upper wick panjang + volume tinggi + harga sempat naik => potensi dump/distribusi.
    distribution_candle = upper_wick_ratio >= 0.03 and volume_ratio_now >= 1.8 and result.change_pct > 0.5

    # MACD status
    if last.get("macd_cross_up", False):
        result.macd_status = "CROSS UP"
    elif last.get("macd_bullish", False):
        result.macd_status = "BULL"
    else:
        result.macd_status = "BEAR"

    # OBV status
    result.obv_status = "ACC" if last.get("obv_bullish", False) else "DIST"
    result.frequency_ratio = float(last.get("frequency_ratio", 1.0) or 1.0)
    result.frequency_curr = float(last.get("frequency", 0.0) or 0.0)
    result.frequency_avg = float(last.get("avg_frequency", 0.0) or 0.0)

    # 3-4. Bandarmology bundle (Ultra broksum 1D)
    bundle = fetch_bandarmology_bundle(symbol)
    broksum = bundle.get("broksum")
    broksum_date = bundle.get("broksum_date")

    bandro = analyze_bandarmology(symbol, bundle, df=bandro_df, broker_chart=None)
    if broksum and bandro:
        bandro.has_broksum = True
        bandro.broksum_date = broksum_date or ""
        bandro.broksum_dominant = broksum.get("dominant", "NEUTRAL")
        bandro.broksum_total_net = float(broksum.get("total_net", 0.0))
        bandro.broksum_top_buyers = broksum.get("top_buyers", []) or []
        bandro.broksum_top_sellers = broksum.get("top_sellers", []) or []
        bandro.broksum_bandar = broksum.get("bandar_accdist", "NEUTRAL")
        bandro.broksum_bandar_raw = broksum.get("bandar_accdist_raw", "") or ""
        bandro.broksum_bandar_source = broksum.get("bandar_source", "") or ""
        bandro.broksum_bandar_amount = float(broksum.get("bandar_amount", 0.0) or 0.0)
        bandro.broksum_bandar_percent = float(broksum.get("bandar_percent", 0.0) or 0.0)
        bandro.broksum_bandar_grand_total = float(broksum.get("bandar_grand_total", 0.0) or 0.0)
        bandro.broksum_bandar_total_value = float(broksum.get("bandar_total_value", 0.0) or 0.0)
        bandro.broksum_total_buyer = int(broksum.get("bandar_total_buyer", 0) or 0)
        bandro.broksum_total_seller = int(broksum.get("bandar_total_seller", 0) or 0)
        bandro.broksum_non_retail_buy_pct = float(broksum.get("non_retail_buy_pct", 0) or 0)
        bandro.broksum_lokal_buy_pct = float(broksum.get("lokal_buy_pct", 0) or 0)
        bandro.broksum_non_retail_net = float(broksum.get("non_retail_net", 0) or 0)
    result.bandro = bandro

    # 5. Scoring hybrid
    score_result        = calculate_score(symbol, df, bandro)
    result.score_result = score_result

    # ═══════════════════════════════════════════════════════
    # SIGNAL DETECTION — sama dengan bot lama v5
    # ═══════════════════════════════════════════════════════
    is_bullish = last.get("direction", -1) == 1
    is_trending = bool(last.get("is_trending", False))

    # ── 1. STRONG BUY ─────────────────────────────────────
    # Breakout confirmed (CONFIRMATION_BARS bar di atas supertrend) + score >= 70
    breakout_up = just_turned_bullish(df)
    if is_bullish:
        bars_above = 0
        for i in range(len(df) - 1, max(len(df) - CONFIRMATION_BARS - 5, 0), -1):
            if df.iloc[i]["direction"] == 1 and df.iloc[i]["close"] > df.iloc[i]["supertrend"]:
                bars_above += 1
            else:
                break
        breakout_confirmed = bars_above >= CONFIRMATION_BARS
    else:
        breakout_confirmed = False

    recent_breakout = breakout_up
    if not recent_breakout:
        for i in range(1, min(CONFIRMATION_BARS + 2, len(df))):
            idx = len(df) - 1 - i
            if idx >= 1:
                if df.iloc[idx - 1]["direction"] == -1 and df.iloc[idx]["direction"] == 1:
                    recent_breakout = True
                    break

    # Cek kondisi broker khusus saat harga minus:
    # Jika harga turun TAPI buyer justru lebih banyak dari seller → skip
    # (penurunan biasa tanpa tanda akumulasi terpusat)
    # Jika harga turun dan buyer lebih sedikit dari seller → lolos
    # (stealth accumulation: bandar akumulasi saat harga ditekan)
    # Jika harga flat/naik → tidak perlu cek broker sama sekali
    _bd     = result.bandro
    _n_buy  = int(getattr(_bd, "broksum_total_buyer",  0) or 0) if _bd else 0
    _n_sell = int(getattr(_bd, "broksum_total_seller", 0) or 0) if _bd else 0
    _no_data = (_n_buy == 0 and _n_sell == 0)

    if result.change_pct < 0 and not _no_data:
        # Harga turun: hanya lolos jika buyer < seller (tanda akumulasi tersembunyi)
        _price_broker_ok = _n_buy < _n_sell
    else:
        # Harga naik/flat atau tidak ada data broker: lolos tanpa syarat broker
        _price_broker_ok = True
    _non_retail_net = float(getattr(_bd, "broksum_non_retail_net", 0.0) or 0.0) if _bd else 0.0
    non_retail_flow_ok = _non_retail_net > 0

    if (is_bullish and (breakout_confirmed or breakout_up)
            and recent_breakout
            and score_result.total_score >= STRONG_BUY_THRESHOLD
            and is_trending
            and _price_broker_ok
            and non_retail_flow_ok
            and not distribution_candle):
        result.is_strong_buy = True

    # ── 2. ACCUMULATION ───────────────────────────────────
    stoch_k         = float(last.get("stoch_k", 50.0))
    stoch_d         = float(last.get("stoch_d", 50.0))
    stoch_cross_up  = bool(last.get("stoch_k_cross_up", False))
    stoch_oversold  = bool(last.get("stoch_oversold", False))

    stoch_buy_trending = is_trending and stoch_cross_up and stoch_k > 20
    stoch_buy_ranging  = not is_trending and stoch_oversold and stoch_cross_up
    smart_stoch_buy    = stoch_buy_trending or stoch_buy_ranging

    acc_momentum = stoch_oversold or smart_stoch_buy
    acc_volume   = bool(last.get("is_volume_spike", False)) or bool(last.get("is_unusual_volume", False))
    not_sideways = not bool(last.get("is_sideways", False))

    # Filter harga turun: buyer harus < seller (stealth acc) agar lolos
    if result.change_pct < 0 and not _no_data:
        _acc_price_ok = _n_buy < _n_sell
    else:
        _acc_price_ok = True

    if (is_bullish and acc_momentum and acc_volume
            and score_result.total_score >= ACCUMULATE_THRESHOLD
            and not_sideways
            and _acc_price_ok
            and non_retail_flow_ok
            and not distribution_candle):
        result.is_accumulation = True

    # ── 3. BULLISH DIVERGENCE ─────────────────────────────
    if last.get("bullish_divergence", False) and not is_bullish:
        strength = int(last.get("div_strength", 0))
        result.div_strength = strength
        result.div_grade    = "STRONG" if strength >= 3 else ("MODERATE" if strength >= 1 else "WEAK")
        result.is_bull_div  = True

    # ── 4. EARLY ENTRY (Serok Bawah) ──────────────────────
    if len(df) >= 2:
        prev_close       = float(df["close"].iloc[-2])
        curr_close       = float(last.get("close", 0))
        drop_from_prev   = ((prev_close - curr_close) / prev_close) * 100 if prev_close > 0 else 0
        result.correction_pct = drop_from_prev

        no_lower_low    = df["low"].iloc[-1] >= df["low"].iloc[-2]
        today_range     = (df["high"].iloc[-1] - df["low"].iloc[-1]) / df["close"].iloc[-1] * 100
        yest_range      = (df["high"].iloc[-2] - df["low"].iloc[-2]) / df["close"].iloc[-2] * 100
        range_shrinking = today_range < yest_range
        low_diff        = abs(df["low"].iloc[-1] - df["low"].iloc[-2]) / df["close"].iloc[-1] * 100
        price_defended  = low_diff < 1.5
        vol_increasing  = df["volume"].iloc[-1] > df["volume"].iloc[-2]
        is_green        = float(last.get("close", 0)) > float(last.get("open", 0)) if "open" in df.columns else False
        body            = abs(float(last.get("close", 0)) - float(last.get("open", 0))) if "open" in df.columns else 0
        wick            = min(float(last.get("close", 0)), float(last.get("open", 0))) - float(last.get("low", 0)) if "open" in df.columns else 0
        wick_rejection  = wick > body * 0.5 if body > 0 else False
        healthy_corr    = bool(last.get("is_healthy_correction", False))

        is_dry_corr     = (3 <= drop_from_prev <= 12) and healthy_corr
        price_holding   = no_lower_low or price_defended or range_shrinking
        early_buying    = vol_increasing or is_green or wick_rejection

        strength = sum([
            is_dry_corr, no_lower_low, price_defended,
            range_shrinking, vol_increasing, is_green, wick_rejection
        ])
        result.early_strength = strength

        # Filter harga turun: buyer harus < seller (stealth acc) agar lolos
        if result.change_pct < 0 and not _no_data:
            _ee_price_ok = _n_buy < _n_sell
        else:
            _ee_price_ok = True

        if is_bullish and is_dry_corr and (price_holding or early_buying) and _ee_price_ok:
            result.is_early_entry = True

    # ── 5. FREQUENCY ANALYZER (TRANSACTION-FIRST, EARLY ENTRY) ──
    # Fokus pada sinyal transaksi dini sebelum markup meledak.
    freq_ratio = float(last.get("frequency_ratio", 1.0) or 1.0)
    freq_spike_today = bool(last.get("is_frequency_spike", False))
    freq_surge_today = bool(last.get("is_frequency_surge", False))
    fa_ratio = float(last.get("freq_analyzer_ratio", 1.0) or 1.0)
    fa_spike_today = bool(last.get("is_freq_analyzer_spike", False))
    fa_surge_today = bool(last.get("is_freq_analyzer_surge", False))
    fa_curr = float(last.get("freq_analyzer", 0.0) or 0.0)
    freq_rising = bool(last.get("frequency_rising", False))
    prev_fa_ratio = float(df.iloc[-2].get("freq_analyzer_ratio", 1.0) or 1.0) if len(df) >= 2 else 1.0
    prev_fa_spike = bool(df.iloc[-2].get("is_freq_analyzer_spike", False)) if len(df) >= 2 else False
    # Match logika lama: trigger FA hanya dari spike indikator freq_analyzer (bukan frequency biasa).
    new_spike_today = fa_spike_today and not prev_fa_spike

    # Guard anti false-spike:
    # Rasio bisa tinggi saat baseline kecil, jadi wajib ada "ukuran bar" yang benar-benar menonjol
    # terhadap riwayat freq_analyzer terbaru (bukan hanya dibanding avg 20).
    fa_recent_peak = 0.0
    fa_recent_mean = 0.0
    fa_size_ok = True
    if "freq_analyzer" in df.columns and len(df) >= 8:
        recent_fa = df["freq_analyzer"].iloc[-21:-1] if len(df) >= 21 else df["freq_analyzer"].iloc[:-1]
        if len(recent_fa) > 0:
            recent_fa = recent_fa.astype(float).fillna(0.0)
            fa_recent_peak = float(recent_fa.max())
            fa_recent_mean = float(recent_fa.mean())
            # Harus minimal setara puncak recent, ATAU jauh di atas rerata recent.
            # Ini menahan sinyal yang ratio tinggi tapi batang aktual kecil.
            fa_size_ok = (
                fa_curr >= (fa_recent_peak * 0.95 if fa_recent_peak > 0 else 0.0)
                or fa_curr >= (fa_recent_mean * 1.8 if fa_recent_mean > 0 else 0.0)
            )

    if len(df) >= 5:
        recent_df = df.iloc[-5:-1]  # konteks 4 hari terakhir sebelum hari ini
    else:
        recent_df = df.iloc[:-1]
    if len(recent_df) > 0 and "frequency_ratio" in recent_df.columns:
        recent_ratios = recent_df["frequency_ratio"].astype(float).fillna(1.0)
        recent_max = float(recent_ratios.max())
        recent_spike_count = int((recent_ratios >= FREQUENCY_SPIKE_THRESHOLD).sum())
    else:
        recent_max = 1.0
        recent_spike_count = 0
    result.frequency_recent_max = recent_max
    result.frequency_recent_spike_count = recent_spike_count

    stoch_cross_up = bool(last.get("stoch_k_cross_up", False))
    macd_cross_up = bool(last.get("macd_cross_up", False))
    vol_ok = bool(last.get("is_volume_spike", False)) or bool(last.get("is_unusual_volume", False))
    # Entry dini: prefer spike frekuensi dengan volume relatif kecil (stealth accumulation).
    volume_ratio = float(last.get("volume_ratio", 1.0) or 1.0)
    stealth_volume_ok = volume_ratio <= 1.3 and not bool(last.get("is_unusual_volume", False))
    result.frequency_stealth_volume_ok = stealth_volume_ok

    # Hindari candle "naik lalu dibanting" dengan volume besar.
    rejection_heavy = distribution_candle or (
        upper_wick_ratio >= 0.03 and volume_ratio >= 1.8 and result.change_pct > 1.0
    )
    price_ok = result.change_pct > -3.5
    pre_markup_ok = result.change_pct <= 3.0 and not result.is_strong_buy
    exploded = result.change_pct >= 6.0

    bandro_ok = False
    bandar_dist = False
    bandar_pct = 0.0
    if result.bandro and result.bandro.has_broksum:
        bandar_pct = float(getattr(result.bandro, "broksum_bandar_percent", 0.0) or 0.0)
        bandar_dist = (getattr(result.bandro, "broksum_bandar", "") in ("DIST", "BIG_DIST"))
        bandro_ok = (
            result.bandro.broksum_bandar == "BIG_ACC"
            or result.bandro.broksum_bandar == "ACC"
            or result.bandro.broksum_dominant == "BUYING"
        )

    momentum_hint = stoch_cross_up or macd_cross_up or (is_bullish and not is_trending)
    foreign_buy_1d = (result.bandro.foreign_dir == "BUYING" and result.bandro.foreign_net_buy > 0) if result.bandro else False
    whale_hint = (result.bandro.freq_signal in ("WHALE", "HIGH_LOT")) if result.bandro else False
    # Gate frequency analyzer: tanpa (bullish & bukan trending) — kondisi itu terlalu sering true.
    momentum_hint_fa = (
        stoch_cross_up or macd_cross_up or bandro_ok or vol_ok or whale_hint
    )

    # Flow score: transaksi dulu, teknikal hanya konfirmasi ringan.
    flow_score = 0
    if freq_spike_today: flow_score += 20
    if fa_spike_today: flow_score += 20
    if freq_surge_today: flow_score += 10
    if fa_surge_today: flow_score += 8
    if freq_rising: flow_score += 8
    if stealth_volume_ok: flow_score += 15
    if recent_spike_count >= 1: flow_score += 8
    if recent_spike_count >= 2: flow_score += 5
    if whale_hint: flow_score += 10
    if bandro_ok: flow_score += 20
    if foreign_buy_1d: flow_score += 8
    if pre_markup_ok: flow_score += 8
    if momentum_hint: flow_score += 6
    if bandar_dist: flow_score -= 15
    if bandar_pct <= -3.0: flow_score -= 10
    if exploded: flow_score -= 25
    if rejection_heavy: flow_score -= 25
    if not stealth_volume_ok: flow_score -= 10

    result.flow_score = max(0, min(100, int(flow_score)))
    # Untuk tampilan FA, utamakan ratio dari freq_analyzer agar konsisten dengan panel.
    result.frequency_ratio = fa_ratio if fa_ratio > 0 else freq_ratio

    strength = sum([
        freq_spike_today or fa_spike_today,
        freq_surge_today,
        fa_surge_today,
        freq_rising,
        recent_spike_count >= 2,
        recent_max >= 3.0,
        stealth_volume_ok,
        pre_markup_ok,
        momentum_hint,
        bandro_ok,
        price_ok,
    ])
    result.frequency_strength = int(strength)

    if result.flow_score >= 70 and pre_markup_ok:
        result.flow_stage = "EARLY_CONFIRM"
    elif result.flow_score >= 55 and pre_markup_ok:
        result.flow_stage = "EARLY_SETUP"
    elif exploded:
        result.flow_stage = "MARKUP_RISK"
    else:
        result.flow_stage = ""

    if (
        fa_spike_today
        and new_spike_today  # alert hanya saat lonjakan BARU freq_analyzer
        and pre_markup_ok
        and price_ok
        and stealth_volume_ok
        and not rejection_heavy
        and fa_size_ok
        and momentum_hint_fa
        and fa_ratio >= FREQ_ANALYZER_SPIKE_THRESHOLD
        and prev_fa_ratio < FREQ_ANALYZER_SPIKE_THRESHOLD
        and strength >= FA_MIN_STRENGTH
        and result.flow_score >= FA_MIN_FLOW_SCORE
    ):
        result.is_frequency_analyzer = True

    return result


def filter_signals(results: list) -> Dict[str, list]:
    """
    Filter hasil scan menjadi kategori sinyal.
    Hanya saham yang memenuhi kondisi yang masuk — sama dengan bot lama.
    """
    signals = {
        "strong_buy":   [],
        "accumulation": [],
        "bull_div":     [],
        "early_entry":  [],
        "frequency_analyzer": [],
        "non_retail_flow": [],
    }

    for r in results:
        # Filter likuiditas — skip saham dengan turnover harian < MIN
        if r.avg_turnover > 0 and r.avg_turnover < MIN_DAILY_TURNOVER:
            logger.debug(f"[{r.symbol}] Skip: turnover rendah {r.avg_turnover/1e9:.1f}B")
            continue

        if r.is_strong_buy:
            signals["strong_buy"].append(r)
        if r.is_accumulation:
            signals["accumulation"].append(r)
        if r.is_bull_div:
            signals["bull_div"].append(r)
        if r.is_early_entry:
            signals["early_entry"].append(r)
        if r.is_frequency_analyzer:
            signals["frequency_analyzer"].append(r)

        # Non-retail flow accumulation — semua kondisi harus terpenuhi:
        #   1. net asing+pemerintah >= NON_RETAIL_FLOW_MIN_PCT dari grand total
        #   2. broksum_bandar = ACC atau BIG_ACC (konsentrasi beli broker ≥25% grand total)
        # Tidak ada filter score — AVOID pun masuk jika smart money akumulasi.
        bd = r.bandro
        if bd and getattr(bd, "has_broksum", False):
            nr_net      = float(getattr(bd, "broksum_non_retail_net", 0) or 0)
            grand_total = float(getattr(bd, "broksum_bandar_grand_total", 0) or 0)
            bandar      = str(getattr(bd, "broksum_bandar", "") or "")
            if nr_net > 0 and grand_total > 0:
                nr_net_pct = nr_net / grand_total * 100.0
                if (nr_net_pct >= NON_RETAIL_FLOW_MIN_PCT
                        and bandar in ("ACC", "BIG_ACC")):
                    signals["non_retail_flow"].append(r)

    for key in signals:
        if key == "non_retail_flow":
            # Urutkan berdasarkan NR net% dari grand total (terbesar di atas)
            def _nr_net_pct(r):
                bd = r.bandro
                if not bd:
                    return 0.0
                nr_net      = float(getattr(bd, "broksum_non_retail_net", 0) or 0)
                grand_total = float(getattr(bd, "broksum_bandar_grand_total", 0) or 0)
                return (nr_net / grand_total * 100.0) if grand_total > 0 else 0.0
            signals[key].sort(key=_nr_net_pct, reverse=True)
        else:
            signals[key].sort(
                key=lambda r: r.score_result.total_score if r.score_result else 0,
                reverse=True
            )

    return signals


def has_any_signal(signals: dict) -> bool:
    """True jika ada minimal satu sinyal dari kategori manapun."""
    return any(len(v) > 0 for v in signals.values())


def filter_intraday_session2_signals(signals: Dict[str, list]) -> Dict[str, list]:
    """
    Filter khusus alert jam 12 (sesi 2):
    - abaikan kandidat yang sudah TP1 / terlalu dekat target,
    - abaikan kandidat yang sudah terlalu naik (extended),
    - fokus kandidat yang masih punya ruang naik.
    """
    selected = {
        "strong_buy": [],
        "accumulation": [],
        "bull_div": [],
        "early_entry": [],
        "frequency_analyzer": [],
    }
    priority = {
        "strong_buy": 5,
        "frequency_analyzer": 4,
        "accumulation": 3,
        "early_entry": 2,
        "bull_div": 1,
    }

    def _upside_to_tp1_pct(r) -> float:
        if float(getattr(r, "tp1", 0.0) or 0.0) <= 0:
            return 999.0
        cp = float(getattr(r, "current_price", 0.0) or 0.0)
        if cp <= 0:
            return -999.0
        return ((float(r.tp1) - cp) / cp) * 100.0

    for key, items in signals.items():
        for r in items or []:
            sr = getattr(r, "score_result", None)
            score = int(getattr(sr, "total_score", 0) or 0)
            if score < INTRADAY_NOON_MIN_SCORE:
                continue

            upside_tp1 = _upside_to_tp1_pct(r)
            if upside_tp1 <= 0:
                # TP1 sudah tercapai/terlewati.
                continue
            if upside_tp1 < INTRADAY_NOON_MIN_UPSIDE_PCT:
                # Terlalu mepet target, risk/reward menurun.
                continue

            if float(getattr(r, "change_pct", 0.0) or 0.0) >= INTRADAY_NOON_MAX_RUNUP_PCT:
                # Sudah naik terlalu tinggi sejak sesi awal.
                continue

            selected[key].append(r)

    for key in selected:
        selected[key].sort(
            key=lambda r: (
                priority.get(key, 0),
                int(getattr(getattr(r, "score_result", None), "total_score", 0) or 0),
                float(getattr(r, "flow_score", 0) or 0.0),
                float(getattr(r, "change_pct", 0) or 0.0),
            ),
            reverse=True,
        )
    return selected

