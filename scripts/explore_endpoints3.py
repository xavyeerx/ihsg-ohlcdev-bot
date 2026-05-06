"""
Explore endpoint IDX RapidAPI dengan URL pattern /api/main/ yang benar.
Jalankan: python scripts/explore_endpoints3.py
"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}
BASE  = f"https://{RAPIDAPI_HOST}"
DELAY = 2.0

# Semua kemungkinan endpoint berdasarkan nama sidebar + pattern /api/main/
CANDIDATES = [
    # Main group
    "/api/main/morning-briefing",
    "/api/main/commodities-impact",
    "/api/main/forex-idr-impact",
    "/api/main/trending-stocks",
    "/api/main/broker-codes",
    "/api/main/idx-symbols",
    "/api/main/search-stocks",

    # Kemungkinan lain dari Global Market group
    "/api/global-market/summary",
    "/api/global-market/indices",
    "/api/global-market/forex",
    "/api/global-market/commodities",

    # Calendar group
    "/api/calendar/events",
    "/api/calendar/corporate-actions",
    "/api/calendar/dividends",

    # Movers dengan pattern /api/main/
    "/api/main/top-gainer",
    "/api/main/top-loser",
    "/api/main/top-volume",
    "/api/main/top-value",
    "/api/main/net-foreign-buy",
    "/api/main/net-foreign-sell",

    # Emiten dengan pattern yang sudah bekerja
    "/api/emiten/BBCA/ohlc-dev",
    "/api/emiten/BBCA/broker-trade-chart",
    "/api/emiten/BBCA/foreign-flow",
    "/api/emiten/BBCA/trade-summary",
    "/api/emiten/BBCA/keystats",
    "/api/emiten/BBCA/summary",
    "/api/emiten/BBCA/profile",
]

print(f"{'URL':<55} Status  Note")
print("-" * 90)
for path in CANDIDATES:
    try:
        r = requests.get(BASE + path, headers=HEADERS, timeout=15)
        status = r.status_code
        if status == 200:
            try:
                data = r.json()
                if isinstance(data, dict):
                    preview = str(list(data.keys())[:5])
                elif isinstance(data, list):
                    preview = f"list[{len(data)}]"
                else:
                    preview = str(data)[:50]
            except:
                preview = r.text[:50]
            print(f"✅ {path:<53} {status}   {preview}")
        elif status == 404:
            print(f"❌ {path:<53} {status}   Not Found")
        elif status == 429:
            print(f"⚠️  {path:<53} {status}   Rate Limited — tunggu 10s...")
            time.sleep(10)
        elif status == 403:
            print(f"🔒 {path:<53} {status}   Forbidden (upgrade plan)")
        else:
            print(f"?? {path:<53} {status}   {r.text[:50]}")
    except Exception as e:
        print(f"ERR {path:<52} {e}")
    time.sleep(DELAY)

print("\nSelesai.")
