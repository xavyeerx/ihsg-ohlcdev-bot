"""
Explore semua endpoint yang tersedia di RapidAPI (plan ULTRA).
Jalankan: python scripts/explore_endpoints.py
Pakai delay 2 detik antar request agar tidak kena rate limit.
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
DELAY = 2.0  # detik antar request

CANDIDATES = [
    # Market overview
    "/api/market/summary",
    "/api/market/indices",
    "/api/market/index",
    "/api/market/status",
    "/api/market/overview",
    "/api/market/composite",

    # Macro
    "/api/macro/morning-briefing",
    "/api/macro/forex-idr-impact",
    "/api/macro/commodities-impact",
    "/api/macro/market-outlook",
    "/api/macro",

    # IDX composite / IHSG
    "/api/ihsg",
    "/api/composite",
    "/api/index/COMPOSITE",
    "/api/index/IDX30",
    "/api/index/LQ45",

    # Movers
    "/api/movers/top-gainer",
    "/api/movers/top-loser",
    "/api/movers/top-volume",
    "/api/movers/top-value",
    "/api/movers/net-foreign-buy",
    "/api/movers/net-foreign-sell",
    "/api/screener/movers",

    # Emiten info
    "/api/emiten/BBCA/keystats",
    "/api/emiten/BBCA/summary",
    "/api/emiten/BBCA/profile",
    "/api/emiten/BBCA/financials",
]

print(f"{'Endpoint':<45} Status  Note")
print("-" * 75)
for path in CANDIDATES:
    try:
        r = requests.get(BASE + path, headers=HEADERS, timeout=15)
        status = r.status_code
        if status == 200:
            marker, note = "✅", "OK"
        elif status == 404:
            marker, note = "❌", "Not Found"
        elif status == 429:
            marker, note = "⚠️ ", "Rate Limited (coba lagi nanti)"
        elif status == 403:
            marker, note = "🔒", "Forbidden (butuh upgrade plan)"
        else:
            marker, note = "??", r.text[:50]
        print(f"{marker} {path:<43} {status}   {note}")
    except Exception as e:
        print(f"ERR {path:<43} {e}")
    time.sleep(DELAY)

print("\nSelesai.")
