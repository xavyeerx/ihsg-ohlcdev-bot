"""
Explore URL pattern alternatif IDX RapidAPI.
Jalankan: python scripts/explore_endpoints2.py
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}
BASE  = f"https://{RAPIDAPI_HOST}"
DELAY = 2.0

# Berbagai format URL yang mungkin dipakai IDX API
CANDIDATES = [
    # Tanpa prefix /api
    "/market/summary",
    "/market/indices",
    "/market/status",
    "/composite",
    "/index/IDX30",
    "/movers/top-gainer",
    "/movers/net-foreign-buy",
    "/emiten/BBCA",
    "/emiten/BBCA/keystats",
    "/emiten/BBCA/summary",

    # Prefix /v1
    "/v1/market/summary",
    "/v1/composite",
    "/v1/movers/top-gainer",
    "/v1/emiten/BBCA",

    # Prefix /v2
    "/v2/market/summary",
    "/v2/composite",

    # Format lain yang umum
    "/stocks/BBCA",
    "/stock/BBCA",
    "/ticker/BBCA",
    "/quote/BBCA",
    "/ohlc/BBCA",
    "/candle/BBCA",

    # Endpoint yang sudah diketahui bekerja (dari bot sebelumnya)
    "/api/emiten/BBCA/ohlc-dev",
    "/api/emiten/BBCA/broker-trade-chart",
    "/api/emiten/BBCA/foreign-flow",
    "/api/emiten/BBCA/trade-summary",
]

print(f"{'Endpoint':<50} Status  Note")
print("-" * 80)
for path in CANDIDATES:
    try:
        r = requests.get(BASE + path, headers=HEADERS, timeout=15)
        status = r.status_code
        if status == 200:
            # Tampilkan preview key dari response
            try:
                import json
                data = r.json()
                if isinstance(data, dict):
                    preview = str(list(data.keys())[:5])
                elif isinstance(data, list):
                    preview = f"list[{len(data)}]"
                else:
                    preview = str(data)[:50]
            except:
                preview = r.text[:50]
            marker, note = "✅", f"OK — keys: {preview}"
        elif status == 404:
            marker, note = "❌", "Not Found"
        elif status == 429:
            marker, note = "⚠️ ", "Rate Limited"
        elif status == 403:
            marker, note = "🔒", "Forbidden (butuh upgrade)"
        else:
            marker, note = "??", r.text[:50]
        print(f"{marker} {path:<48} {status}   {note}")
    except Exception as e:
        print(f"ERR {path:<48} {e}")
    time.sleep(DELAY)

print("\nSelesai.")
