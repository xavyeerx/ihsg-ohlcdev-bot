#!/usr/bin/env python3
"""
CHECK DELAY -- Bandingkan timestamp candle terakhir vs waktu sekarang
Jalankan saat market BUKA (09:00-15:30 WIB) untuk hasil akurat.

Usage:
    python scripts/check_delay.py           # default: BBCA, interval 1m
    python scripts/check_delay.py BBRI 5m   # custom symbol & interval
"""

import sys, os, json, requests
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

SYMBOL   = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
INTERVAL = sys.argv[2] if len(sys.argv) > 2 else "1m"
LIMIT    = 5

WIB = timezone(timedelta(hours=7))

headers = {
    "X-RapidAPI-Key":  RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}

# Helper: ambil unix timestamp dari satu candle dict
def get_ts(c):
    raw = (c.get("unix_timestamp") or c.get("unixdate") or
           c.get("t") or c.get("timestamp") or 0)
    return int(raw) if raw else 0

# Cari list candle secara rekursif dalam nested response
def find_candles(obj, depth=0):
    if depth > 6: return None
    if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
        keys = set(obj[0].keys())
        if keys & {"open", "high", "low", "close", "o", "h", "l", "c"}:
            return obj
    if isinstance(obj, dict):
        for key in ("chartbit", "candles", "chart", "ohlcv", "bars", "data", "result"):
            if key in obj:
                found = find_candles(obj[key], depth + 1)
                if found is not None:
                    return found
    return None

# ── Fetch ────────────────────────────────────────────────
print("=" * 55)
print(f"  Delay Check — {SYMBOL} [{INTERVAL}]")
print("=" * 55)

now_utc = datetime.now(timezone.utc)
now_wib = now_utc.astimezone(WIB)
print(f"  Waktu sekarang (WIB) : {now_wib.strftime('%Y-%m-%d %H:%M:%S')}")

url  = f"https://{RAPIDAPI_HOST}/api/chart/{SYMBOL}/{INTERVAL}/latest"
resp = requests.get(url, headers=headers, params={"limit": LIMIT}, timeout=15)
print(f"  HTTP status          : {resp.status_code}")

if resp.status_code != 200:
    print(f"  ERROR: {resp.text[:200]}")
    sys.exit(1)

data    = resp.json()
candles = find_candles(data)

if not candles:
    print("  ERROR: candle tidak ditemukan dalam response")
    print(f"  Raw keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    sys.exit(1)

# ── Info urutan data ──────────────────────────────────────
print(f"\n  Jumlah candle diterima : {len(candles)}")
print(f"  Kolom candle           : {list(candles[0].keys())}")
ts0    = get_ts(candles[0])
ts_end = get_ts(candles[-1])
order  = "descending (terbaru di index 0)" if ts0 > ts_end else "ascending (terbaru di index -1)"
print(f"  Urutan data            : {order}")
print()

# Candle terbaru = yang punya timestamp terbesar
last           = candles[0] if ts0 > ts_end else candles[-1]
candles_sorted = sorted(candles, key=get_ts)   # ascending untuk tabel

# ── Hitung delay ──────────────────────────────────────────
ts_raw = get_ts(last)
dt_str = last.get("datetime") or last.get("date") or last.get("d") or ""

if ts_raw:
    unit       = "ms" if ts_raw > 1e11 else "s"
    ts_sec     = ts_raw / 1000 if unit == "ms" else ts_raw
    candle_utc = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
    candle_wib = candle_utc.astimezone(WIB)
    delay_sec  = (now_utc - candle_utc).total_seconds()

    print(f"  Candle terbaru (WIB)  : {candle_wib.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  String tanggal API    : {dt_str}")
    print(f"  Delay dari sekarang   : {delay_sec:.0f} detik  ({delay_sec/60:.1f} menit)")
    print()

    if delay_sec < 120:
        print("  ✅ REALTIME / near-realtime (delay < 2 menit)")
    elif delay_sec < 600:
        print(f"  ⚠️  DELAYED ~{delay_sec/60:.0f} menit")
    elif delay_sec < 3600:
        print(f"  ❌ DELAY SIGNIFIKAN ~{delay_sec/60:.0f} menit")
    else:
        print(f"  ❌ DATA LAMA — candle terakhir dari {delay_sec/3600:.1f} jam lalu")
else:
    print("  WARNING: tidak ada kolom timestamp di candle")
    print(f"  Raw candle terbaru: {json.dumps(last, indent=4)}")

# ── Tabel candle ──────────────────────────────────────────
print()
print(f"  {LIMIT} candle (lama → baru):")
print(f"  {'No':>3}  {'Timestamp WIB':<22}  {'Open':>8}  {'High':>8}  {'Low':>8}  {'Close':>8}  {'Volume':>12}")
print("  " + "-" * 80)
for i, c in enumerate(candles_sorted):
    ts_c = get_ts(c)
    if ts_c:
        ts_sec_c = ts_c / 1000 if ts_c > 1e11 else ts_c
        dt_c     = datetime.fromtimestamp(ts_sec_c, tz=timezone.utc).astimezone(WIB)
        dt_str_c = dt_c.strftime('%Y-%m-%d %H:%M:%S')
    else:
        dt_str_c = c.get("datetime") or c.get("date", "?")
    o  = c.get("open",   c.get("o", "-"))
    h  = c.get("high",   c.get("h", "-"))
    l  = c.get("low",    c.get("l", "-"))
    cl = c.get("close",  c.get("c", "-"))
    v  = c.get("volume", c.get("v", "-"))
    print(f"  {i+1:>3}  {dt_str_c:<22}  {str(o):>8}  {str(h):>8}  {str(l):>8}  {str(cl):>8}  {str(v):>12}")

print()
print("  Bandingkan close candle terbaru dengan harga di Stockbit/RTI")
print("  pada waktu yang sama untuk konfirmasi akurasi harga.")
print("=" * 55)
