"""
Test semua endpoint dengan pola query param: /api/emiten/{endpoint}?symbol=BBCA
Ditemukan dari sniff: /api/emiten/running-trade?symbol=BBCA → 200!

Jalankan: python scripts/probe_query_param_style.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
BASE    = f"https://{RAPIDAPI_HOST}"
DELAY   = 1.5

def get(path, params=None):
    try:
        r = requests.get(BASE + path, headers=HEADERS, params=params or {}, timeout=15)
        try:    body = r.json()
        except: body = {"raw": r.text[:300]}
        return r.status_code, body, r
    except Exception as e:
        return 0, {"error": str(e)}, None

SYM = "BBCA"

print("=" * 80)
print(f"PROBE: Query Param Style — ?symbol={SYM}")
print("=" * 80)

# Semua suffix yang perlu dicek — kombinasi path-param dan query-param style
endpoints = [
    # --- Emiten (yang dulu path-param /api/emiten/{SYM}/...) ---
    ("/api/emiten/running-trade",           {"symbol": SYM}),
    ("/api/emiten/all-insider-trading",     {"symbol": SYM}),
    ("/api/emiten/holding-composition",     {"symbol": SYM}),
    ("/api/emiten/insider-trading",         {"symbol": SYM}),
    ("/api/emiten/insider",                 {"symbol": SYM}),
    ("/api/emiten/foreign-ownership",       {"symbol": SYM}),
    ("/api/emiten/orderbook",               {"symbol": SYM}),
    ("/api/emiten/seasonality",             {"symbol": SYM}),
    ("/api/emiten/historical-summary",      {"symbol": SYM}),
    ("/api/emiten/financials",              {"symbol": SYM}),
    ("/api/emiten/keystats",                {"symbol": SYM}),
    ("/api/emiten/tradebook-chart",         {"symbol": SYM}),
    ("/api/emiten/broker-trade-chart",      {"symbol": SYM}),
    ("/api/emiten/subsidiary",              {"symbol": SYM}),
    ("/api/emiten/info",                    {"symbol": SYM}),
    ("/api/emiten/profile-background",      {"symbol": SYM}),
    ("/api/emiten/fundachart-metrics",      {"symbol": SYM}),
    ("/api/emiten/fundachart",              {"symbol": SYM}),
    ("/api/emiten/key-ratios",              {"symbol": SYM}),
    ("/api/emiten/insights",                {"symbol": SYM}),
    ("/api/emiten/earnings",                {"symbol": SYM}),
    ("/api/emiten/ohlcv",                   {"symbol": SYM}),
    ("/api/emiten/broker-summary",          {"symbol": SYM}),
    ("/api/emiten/broksum",                 {"symbol": SYM}),
    ("/api/emiten/technical-analysis",      {"symbol": SYM}),
    ("/api/emiten/risk-reward",             {"symbol": SYM}),
    # --- Chart (dulu /api/chart/ohlcv?symbol=) ---
    ("/api/chart/ohlcv",                    {"symbol": SYM}),
    ("/api/chart/latest-ohlcv",             {"symbol": SYM}),
    ("/api/emiten/chart",                   {"symbol": SYM}),
    ("/api/emiten/price",                   {"symbol": SYM}),
    # --- Market Detector (dulu /api/market-detector/broker-summary) ---
    ("/api/market-detector/broker-summary", {}),
    ("/api/market-detector/broker-summary", {"symbol": SYM}),
    ("/api/market-detector/top-brokers",    {}),
    ("/api/market-detector/top-stocks",     {}),
    ("/api/market-detector/broker-activity",{}),
    # --- Main ---
    ("/api/main/idx-symbols",               {}),
    ("/api/main/search-stocks",             {"q": SYM}),
    ("/api/main/trending-stocks",           {}),
    # --- Movers ---
    ("/api/movers/market",                  {}),
    # --- Sectors ---
    ("/api/sectors/all",                    {}),
    ("/api/sectors/companies",              {"sector": "banking"}),
    # --- Advanced ---
    ("/api/advanced/whale-transactions",    {}),
    ("/api/advanced/whale-transactions",    {"symbol": SYM}),
    ("/api/advanced/insider-screening",     {}),
    ("/api/advanced/insider-net-summary",   {}),
    ("/api/advanced/technical-analysis",    {"symbol": SYM}),
    ("/api/advanced/multi-market-screener", {}),
    # --- Bandarmology ---
    ("/api/bandarmology/distribution",      {}),
    ("/api/bandarmology/accumulation",      {}),
    ("/api/bandarmology/smart-money-flow",  {}),
    ("/api/bandarmology/pump-dump",         {}),
    # --- Retail Opportunity ---
    ("/api/retail-opportunity/sector-rotation", {}),
    ("/api/retail-opportunity/breakout-alerts", {}),
    ("/api/retail-opportunity/risk-reward",     {"symbol": SYM}),
    ("/api/retail-opportunity/multibagger",     {}),
    # --- Market Sentiment ---
    ("/api/market-sentiment/retail-bandar", {}),
    # --- Global Market ---
    ("/api/global-market/overview",         {}),
    ("/api/global-market/impact-analysis",  {}),
    ("/api/global-market/indices-impact",   {}),
    # --- Calendar ---
    ("/api/calendar/dividend",              {}),
    ("/api/calendar/corporate-actions",     {}),
    ("/api/calendar/ipo",                   {}),
    ("/api/calendar/economic",              {}),
]

active = []
for path, params in endpoints:
    s, body, r = get(path, params)
    param_str = f"?{'&'.join(f'{k}={v}' for k,v in params.items())}" if params else ""
    full = path + param_str

    if s == 200:
        print(f"\n✅ [{s}] {full}")
        if isinstance(body, dict):
            data = body.get("data", body)
            if isinstance(data, list):
                print(f"   list[{len(data)}]", end="")
                if data and isinstance(data[0], dict):
                    print(f" — sample keys: {list(data[0].keys())[:7]}", end="")
                print()
            elif isinstance(data, dict):
                keys = list(data.keys())
                print(f"   dict keys: {keys[:8]}")
                # Tunjukkan sample value untuk running-trade
                if "running_trade" in data:
                    rt = data["running_trade"]
                    if isinstance(rt, list) and rt:
                        print(f"   running_trade[0]: {json.dumps(rt[0], ensure_ascii=False)[:200]}")
            else:
                print(f"   {str(data)[:100]}")
        active.append((path, params))
    elif s != 404 and s != 0:
        print(f"[{s}] {full}")
    time.sleep(DELAY)

print()
print("=" * 80)
print(f"RINGKASAN: {len(active)} endpoint aktif")
print("=" * 80)
for path, params in active:
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    print(f"  ✅ {path}" + (f"?{param_str}" if param_str else ""))

print()
print("Paste output ini ke chat — akan digunakan untuk update data_fetcher.py")
