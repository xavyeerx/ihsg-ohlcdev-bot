#!/usr/bin/env python3
# Debug raw response API -- jalankan dari folder ihsg-ohlcdev-bot
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST
import requests

headers = {
    "X-RapidAPI-Key":  RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}
url = f"https://{RAPIDAPI_HOST}/api/chart/BBCA/daily/latest"
resp = requests.get(url, headers=headers, params={"limit": 5}, timeout=15)
print(f"Status: {resp.status_code}")

data = resp.json()
# Telusuri sampai ke chartbit
def find_chartbit(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            result = find_chartbit(v, f"{path}.{k}")
            if result:
                return result
        return None
    if isinstance(obj, list) and len(obj) > 0:
        print(f"\nFound list at {path}, len={len(obj)}")
        print(f"First item keys: {list(obj[0].keys()) if isinstance(obj[0], dict) else type(obj[0])}")
        print(f"First item: {json.dumps(obj[0], indent=2)}")
        return obj
    return None

find_chartbit(data)
