#!/usr/bin/env python3
"""
Eksplorasi struktur lengkap getBrokerTradeChart
Jalankan: python scripts/explore_broker_chart.py
"""
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

SYMBOL  = "BBCA"
HEADERS = {
    "X-RapidAPI-Key":  RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}

url = f"https://{RAPIDAPI_HOST}/api/emiten/{SYMBOL}/broker-trade-chart"
print(f"Fetching: {url}\n")

r = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status: {r.status_code}\n")
if r.status_code != 200:
    print(r.text[:300]); sys.exit(1)

data = r.json()

# Simpan raw JSON supaya bisa dibaca manual
out_path = os.path.join(os.path.dirname(__file__), "broker_chart_raw.json")
with open(out_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"[Raw JSON saved] → {out_path}\n")

d = data.get("data", {})

print("=" * 60)
print("TOP LEVEL")
print("=" * 60)
for k, v in d.items():
    if isinstance(v, list):
        print(f"  {k}: list[{len(v)}]")
    elif isinstance(v, dict):
        print(f"  {k}: dict({list(v.keys())})")
    else:
        print(f"  {k}: {repr(v)}")

print()
print("=" * 60)
print("price_chart_data — semua item")
print("=" * 60)
pcd = d.get("price_chart_data", [])
for item in pcd:
    print(f"  {item}")

print()
print("=" * 60)
print("broker_chart_data — semua item (full depth)")
print("=" * 60)
bcd = d.get("broker_chart_data", [])
print(f"Total: {len(bcd)} entries\n")
for i, entry in enumerate(bcd):
    print(f"--- Entry [{i}] ---")
    for k, v in entry.items():
        if isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
            for j, item in enumerate(v[:5]):   # tampilkan 5 item pertama
                print(f"    [{j}] {item}")
            if len(v) > 5:
                print(f"    ... ({len(v)-5} more)")
        elif isinstance(v, dict):
            print(f"  {k}: {{")
            for kk, vv in list(v.items())[:10]:
                print(f"    {kk}: {repr(vv)}")
            if len(v) > 10:
                print(f"    ... ({len(v)-10} more keys)")
            print("  }")
        else:
            print(f"  {k}: {repr(v)}")
    print()
