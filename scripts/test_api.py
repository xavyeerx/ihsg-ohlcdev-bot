#!/usr/bin/env python3
# TEST API -- Verifikasi koneksi + pipeline lengkap (mode: daily)
# Jalankan: python scripts/test_api.py

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST, OHLCV_INTERVAL
from core.data_fetcher import fetch_ohlcv, fetch_stock_info, fetch_bandarmology_bundle
from core.bandarmology import analyze_bandarmology
from core.supertrend import calculate_supertrend
from core.indicators import calculate_all_indicators
from core.scoring import calculate_score
import pandas as pd

TEST_SYMBOL = "BBCA"

print("=" * 57)
print("  IDX Market Intelligence API -- Connection Test")
print("=" * 57)
print(f"  API Host : {RAPIDAPI_HOST}")
print(f"  API Key  : {RAPIDAPI_KEY[:8]}...{RAPIDAPI_KEY[-4:]}")
print(f"  Symbol   : {TEST_SYMBOL}")
print(f"  Interval : {OHLCV_INTERVAL}")
print("=" * 57)

# ------ 1. OHLCV ------
print("\n[1] Fetch OHLCV data ...")
df = fetch_ohlcv(TEST_SYMBOL, interval=OHLCV_INTERVAL, limit=150)
if df is not None and len(df) >= 5:
    print(f"  OK  OHLCV -- {len(df)} bar diterima")
    print(f"      Kolom    : {list(df.columns)}")
    print(f"      Terakhir : close={df['close'].iloc[-1]:,.0f}  "
          f"high={df['high'].iloc[-1]:,.0f}  low={df['low'].iloc[-1]:,.0f}")
    print(f"      Volume   : {float(df['volume'].iloc[-1]):,.0f}")

    # -- Cek foreign flow di data daily (kolom sudah di-rename oleh data_fetcher) --
    print(f"\n  -- Foreign Flow (dari {len(df)} bar) --")
    if 'foreign_buy' in df.columns and 'foreign_sell' in df.columns:
        fb  = df['foreign_buy'].astype(float)
        fs  = df['foreign_sell'].astype(float)
        net = fb - fs
        nonzero_fb = (fb != 0).sum()
        nonzero_fs = (fs != 0).sum()
        print(f"      foreign_buy  nonzero : {nonzero_fb}/{len(df)} bar")
        print(f"      foreign_sell nonzero : {nonzero_fs}/{len(df)} bar")
        if nonzero_fb > 0:
            print(f"      Net 5 bar terakhir  : {net.iloc[-5:].sum():+,.0f}")
            print(f"      Net 20 bar terakhir : {net.iloc[-20:].sum():+,.0f}")
            print(f"      Foreign % vol (20b) : {fb.iloc[-20:].sum() / df['volume'].astype(float).iloc[-20:].sum():.1%}")
            pd.set_option('display.float_format', '{:,.0f}'.format)
            cols = [c for c in ['close','volume','foreign_buy','foreign_sell'] if c in df.columns]
            print(f"\n      5 bar terakhir:")
            print(df[cols].tail(5).to_string())
        else:
            print(f"      PERHATIAN: foreign_buy/sell = 0 di semua bar")
    elif 'foreign_flow' in df.columns:
        ff = df['foreign_flow'].astype(float)
        nonzero_ff = (ff != 0).sum()
        print(f"      foreign_flow (net Rp) nonzero : {nonzero_ff}/{len(df)} bar")
        if nonzero_ff > 0:
            print(f"      Net 5 bar terakhir  : {ff.iloc[-5:].sum():+,.0f}")
            print(f"      Net 20 bar terakhir : {ff.iloc[-20:].sum():+,.0f}")
            pd.set_option('display.float_format', '{:,.0f}'.format)
            cols = [c for c in ['close','volume','foreign_flow'] if c in df.columns]
            print(f"\n      5 bar terakhir:")
            print(df[cols].tail(5).to_string())
    else:
        print(f"      Kolom foreign tidak ditemukan di data")

    if 'frequency' in df.columns:
        freq = df['frequency'].astype(float)
        print(f"\n  -- Frequency --")
        print(f"      min={freq.min():.0f}  max={freq.max():.0f}  mean={freq.mean():.0f}")
        print(f"      5 bar terakhir: {list(freq.iloc[-5:].astype(int))}")

else:
    print("  GAGAL  OHLCV -- data tidak cukup atau None")

# ------ 2. Stock Info ------
print("\n[2] Fetch Stock Info ...")
info = fetch_stock_info(TEST_SYMBOL)
if info:
    print(f"  OK  Stock Info")
    print(f"      Name   : {info.get('name', info.get('emiten_name', 'N/A'))}")
    print(f"      Sector : {info.get('sector', info.get('sektor', 'N/A'))}")
else:
    print("  GAGAL  Stock Info")

# ------ 3. Broker endpoint ------
print("\n[3] Broker / Movers ...")
print("  INFO  Bundle bandarmology mengambil:")
print("        - Broker Summary 1D (Ultra, fallback jika hari ini belum tersedia)")
print("        - Broker Trade Chart (multi-hari, jika diaktifkan di settings)")

# ------ 4. Full Pipeline ------
print("\n[4] Full Pipeline (Supertrend + Indikator + Bandarmology + Scoring) ...")
if df is not None and len(df) >= 50:
    try:
        df2 = calculate_supertrend(df.copy())
        df2 = calculate_all_indicators(df2)

        bundle = fetch_bandarmology_bundle(TEST_SYMBOL)
        bandro = analyze_bandarmology(TEST_SYMBOL, bundle, df=df2)
        score_result = calculate_score(TEST_SYMBOL, df2, bandro)

        last = df2.iloc[-1]
        direction = "BULLISH" if last.get("direction", -1) == 1 else "BEARISH"

        print(f"  OK  Pipeline")
        print(f"\n  -- TEKNIKAL ({score_result.technical_total:.1f}/70) --")
        print(f"      Status      : {score_result.status}")
        print(f"      Total Score : {score_result.total_score}/100")
        print(f"      Trend       : {score_result.trend_score:.1f}/25")
        print(f"      Regime      : {score_result.regime_score:.1f}/12")
        print(f"      Volume      : {score_result.volume_score:.1f}/18")
        print(f"      Momentum    : {score_result.momentum_score:.1f}/25")
        print(f"      Position    : {score_result.position_score:.1f}/15")
        print(f"      Pattern     : {score_result.pattern_score:.1f}/5")
        print(f"      Supertrend  : {last.get('supertrend', 0):,.0f}  [{direction}]")
        print(f"      TP1 / TP2   : {last.get('tp1',0):,.0f} / {last.get('tp2',0):,.0f}")
        print(f"      Bullish Break: {'YA' if last.get('bullish_break') else 'Tidak'}")

        print(f"\n  -- VOLUME INTELLIGENCE / BANDARMOLOGY ({bandro.score}/30) --")
        print(f"      Sinyal       : {bandro.accum_signal}")
        print(f"      Vol Trend    : {bandro.vol_trend}  (ratio {bandro.vol_ratio:.2f}x)")
        print(f"      Absorbsi     : {'YA -- bandar serap' if bandro.absorption else 'Tidak'}")
        print(f"      Freq Signal  : {bandro.freq_signal}")
        print(f"      Foreign Dir  : {bandro.foreign_dir}")
        if bandro.foreign_net_buy != 0:
            net_rp = bandro.foreign_net_buy
            net_t  = net_rp / 1e12
            sell_pct = (1 - bandro.foreign_pct) * 100
            buy_pct  = bandro.foreign_pct * 100
            print(f"      Net Foreign  : {net_rp:+,.0f} Rp  ({net_t:+.2f}T)")
            print(f"      Komposisi    : Beli {buy_pct:.1f}% vs Jual {sell_pct:.1f}% dari total txn asing")
        print(f"      Is Accumulating : {bandro.is_accumulating}")
        print(f"      Is Distributing : {bandro.is_distributing}")
        print(f"      Breakdown    : {bandro.score_breakdown}")

    except Exception as e:
        print(f"  ERROR  Pipeline: {e}")
        import traceback; traceback.print_exc()
elif df is not None:
    print(f"  INFO  Data {len(df)} bar -- butuh >=50 untuk pipeline penuh")
else:
    print("  SKIP  OHLCV gagal di-fetch")

print("\n" + "=" * 57)
print("  Test selesai. Jika OK, jalankan: python main.py")
print("=" * 57)
