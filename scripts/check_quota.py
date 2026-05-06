"""
Cek sisa quota RapidAPI bulan ini via response headers.
Jalankan: python scripts/check_quota.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}

# Hit 1 endpoint ringan saja untuk baca headers quota
r = requests.get(
    f"https://{RAPIDAPI_HOST}/api/emiten/BBCA/ohlc-dev",
    headers=HEADERS,
    params={"interval": "daily", "limit": 1},
    timeout=15,
)

print(f"Status: {r.status_code}")
print("\n--- Quota Headers ---")
for k, v in r.headers.items():
    if any(x in k.lower() for x in ["limit", "remain", "quota", "reset", "usage", "rapid"]):
        print(f"  {k}: {v}")
