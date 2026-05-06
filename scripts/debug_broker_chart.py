"""
Debug struktur data getBrokerTradeChart secara detail.
Jalankan: python scripts/debug_broker_chart.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}

symbol = "BBCA"
r = requests.get(
    f"https://{RAPIDAPI_HOST}/api/emiten/{symbol}/broker-trade-chart",
    headers=HEADERS,
    timeout=15,
)

raw = r.json()
data = raw.get("data", raw)  # masuk ke level 'data'

print(f"Keys di 'data': {list(data.keys()) if isinstance(data, dict) else type(data)}")
print(f"from: {data.get('from')}  to: {data.get('to')}")

# Tampilkan broker_chart_data
bcd = data.get("broker_chart_data", [])
print(f"\nbroker_chart_data: {len(bcd)} entries")

for i, entry in enumerate(bcd):
    etype = entry.get("type", "?")
    charts = entry.get("charts", [])
    print(f"\n  Entry [{i}] type={etype}, {len(charts)} brokers")

    for bc in charts:
        code    = bc.get("broker_code", "?")
        candles = bc.get("chart", [])
        print(f"\n    Broker {code}: {len(candles)} candles")
        for c in candles[:6]:
            raw_val = c.get("value", {}).get("raw", "0")
            fmt_val = c.get("value", {}).get("formatted", "?")
            print(f"      {c.get('date')} {c.get('time',''):>6}  raw={raw_val:>20}  fmt={fmt_val}")
        if len(candles) > 6:
            print(f"      ... +{len(candles)-6} candles")
        total = sum(float(str(c.get("value",{}).get("raw","0")).replace(",","")) for c in candles)
        print(f"      SUM all candles = {total:,.0f}")
        # Nilai candle terakhir per hari
        by_date = {}
        for c in candles:
            by_date[c.get("date")] = float(str(c.get("value",{}).get("raw","0")).replace(",",""))
        last_per_day = sum(by_date.values())
        print(f"      SUM last-per-day = {last_per_day:,.0f}  ({list(by_date.items())})")
