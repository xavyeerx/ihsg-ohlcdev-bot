"""
Rediscover semua path API yang benar — karena provider tampaknya mengubah base path.
Endpoint yang dulu /api/chart/ohlcv sekarang mungkin /v2/chart/ohlcv atau prefix lain.

Jalankan: python scripts/rediscover_all_paths.py
PENTING: Output ini akan digunakan untuk update core/data_fetcher.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
BASE    = f"https://{RAPIDAPI_HOST}"
DELAY   = 1.2

def get(path, params=None):
    try:
        r = requests.get(BASE + path, headers=HEADERS, params=params or {}, timeout=15)
        try:    body = r.json()
        except: body = {"raw": r.text[:300]}
        return r.status_code, body
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 80)
print("FASE 1: Temukan prefix yang benar untuk endpoint OHLCV (sudah diketahui berhasil)")
print("=" * 80)

# OHLCV adalah benchmark — kita tahu ini HARUS ada, cari prefixnya
ohlcv_candidates = [
    # Format lama
    ("/api/chart/ohlcv",                {"symbol": "BBCA"}),
    # Format baru kemungkinan
    ("/api/v2/chart/ohlcv",             {"symbol": "BBCA"}),
    ("/v2/api/chart/ohlcv",             {"symbol": "BBCA"}),
    ("/api/ohlcv",                      {"symbol": "BBCA"}),
    ("/api/chart/ohlcv/BBCA",           {}),
    ("/api/emiten/BBCA/ohlcv",          {}),
    ("/api/emiten/BBCA/chart",          {}),
    ("/api/emiten/BBCA/ohlc",           {}),
    ("/api/emiten/BBCA/historical",     {}),
    ("/api/emiten/BBCA/price-history",  {}),
    ("/api/emiten/BBCA/candlestick",    {}),
    ("/api/chart",                      {"symbol": "BBCA"}),
    ("/api/latest-ohlcv",               {"symbol": "BBCA"}),
    ("/api/emiten/BBCA/latest-ohlcv",   {}),
    ("/api/chart/latest-ohlcv",         {"symbol": "BBCA"}),
    ("/api/emiten/BBCA/price",          {}),
    ("/api/price",                      {"symbol": "BBCA"}),
]

found_ohlcv = None
for path, params in ohlcv_candidates:
    s, body = get(path, params)
    if s == 200:
        print(f"✅ OHLCV FOUND: {path} params={params}")
        if isinstance(body, dict):
            data = body.get("data", body)
            if isinstance(data, list) and data:
                print(f"   Sample keys: {list(data[0].keys())[:6] if isinstance(data[0], dict) else data[0]}")
        found_ohlcv = (path, params)
        break
    elif s != 404:
        print(f"[{s}] {path}")
    time.sleep(DELAY)

if not found_ohlcv:
    print("⚠️ OHLCV tidak ditemukan dengan semua kandidat path")

print()
print("=" * 80)
print("FASE 2: Temukan prefix untuk broker-summary")
print("=" * 80)

broksum_candidates = [
    ("/api/market-detector/broker-summary",         {}),
    ("/api/v2/market-detector/broker-summary",      {}),
    ("/api/emiten/BBCA/broker-summary",             {}),
    ("/api/emiten/BBCA/broksum",                    {}),
    ("/api/broksum",                                {"symbol": "BBCA"}),
    ("/api/broker-summary",                         {"symbol": "BBCA"}),
    ("/api/emiten/BBCA/brokers",                    {}),
    ("/api/emiten/BBCA/broker",                     {}),
    ("/api/market-detector/broksum",                {"symbol": "BBCA"}),
    ("/api/brokerage",                              {"symbol": "BBCA"}),
    ("/api/emiten/BBCA/brokerage-summary",          {}),
]

for path, params in broksum_candidates:
    s, body = get(path, params)
    if s == 200:
        print(f"✅ BROKSUM FOUND: {path} params={params}")
        if isinstance(body, dict):
            data = body.get("data", body)
            if isinstance(data, list) and data:
                sample = data[0] if data else {}
                print(f"   Sample keys: {list(sample.keys())[:8] if isinstance(sample, dict) else sample}")
        break
    elif s != 404:
        print(f"[{s}] {path}")
    time.sleep(DELAY)

print()
print("=" * 80)
print("FASE 3: Temukan semua endpoint /api/emiten/BBCA/* yang AKTIF")
print("=" * 80)

# Test semua suffix emiten yang ada di sidebar + variasi
emiten_suffixes = [
    # --- Yang diketahui AKTIF ---
    "foreign-ownership",
    "insider",          # ditemukan tadi!
    # --- Yang perlu dikonfirmasi ---
    "running-trade",
    "all-insider-trading",
    "holding-composition",
    "orderbook",
    "seasonality",
    "historical-summary",
    "financials",
    "keystats",
    "tradebook-chart",
    "broker-trade-chart",
    "subsidiary",
    "info",
    "profile-background",
    "fundachart-metrics",
    "fundachart",
    "key-ratios",
    "insights",
    "earnings",
    "ohlcv",
    "chart",
    "price",
    "broksum",
    "broker-summary",
    "technical-analysis",
    "risk-reward",
    # Variasi path yang 404 sebelumnya
    "insiders",
    "insider-trading",
    "holding",
    "holdings",
    "shareholders",
    "shareholder",
    "ownership",
    "composition",
    "running",
    "trades",
    "trade",
    "whale",
]

print(f"\nTesting {len(emiten_suffixes)} endpoint suffix untuk /api/emiten/BBCA/...\n")
active_emiten = []
for suffix in emiten_suffixes:
    path = f"/api/emiten/BBCA/{suffix}"
    s, body = get(path)
    if s == 200:
        print(f"✅ [{s}] {path}")
        if isinstance(body, dict):
            data = body.get("data", body)
            if isinstance(data, list):
                print(f"       list[{len(data)}]", end="")
                if data and isinstance(data[0], dict):
                    print(f" keys: {list(data[0].keys())[:6]}", end="")
            elif isinstance(data, dict):
                print(f"       keys: {list(data.keys())[:8]}", end="")
            print()
        active_emiten.append(suffix)
    elif s != 404:
        print(f"[{s}] {path}")
    time.sleep(DELAY)

print()
print("=" * 80)
print("FASE 4: Test global endpoints (non-emiten)")
print("=" * 80)

global_candidates = [
    # Main
    ("/api/main/idx-symbols",                   {}),
    ("/api/main/search-stocks",                 {"q": "BBCA"}),
    ("/api/main/trending-stocks",               {}),
    ("/api/main/broker-codes",                  {}),
    # Chart
    ("/api/chart/ohlcv",                        {"symbol": "BBCA"}),
    ("/api/chart/latest-ohlcv",                 {"symbol": "BBCA"}),
    # Market Detector
    ("/api/market-detector/broker-summary",     {}),
    ("/api/market-detector/top-brokers",        {}),
    ("/api/market-detector/top-stocks",         {}),
    ("/api/market-detector/broker-activity",    {}),
    # Movers
    ("/api/movers/market",                      {}),
    # Sectors
    ("/api/sectors/all",                        {}),
    ("/api/sectors/sub-sectors",                {}),
    # Retail Opportunity
    ("/api/retail-opportunity/sector-rotation", {}),
    ("/api/retail-opportunity/breakout-alerts", {}),
    # Calendar
    ("/api/calendar/dividend",                  {}),
    ("/api/calendar/corporate-actions",         {}),
    # Market Sentiment
    ("/api/market-sentiment/retail-bandar",     {}),
    # Bandarmology
    ("/api/bandarmology/distribution",          {}),
    ("/api/bandarmology/accumulation",          {}),
    ("/api/bandarmology/smart-money-flow",      {}),
    ("/api/bandarmology/pump-dump",             {}),
    # Advanced
    ("/api/advanced/whale-transactions",        {}),
    ("/api/advanced/insider-screening",         {}),
    ("/api/advanced/technical-analysis",        {"symbol": "BBCA"}),
    # Global Market
    ("/api/global-market/overview",             {}),
    ("/api/global-market/impact-analysis",      {}),
]

active_global = []
for path, params in global_candidates:
    s, body = get(path, params)
    if s == 200:
        print(f"✅ [{s}] {path}")
        if isinstance(body, dict):
            data = body.get("data", body)
            if isinstance(data, list):
                print(f"       list[{len(data)}]")
            elif isinstance(data, dict):
                print(f"       keys: {list(data.keys())[:6]}")
        active_global.append(path)
    elif s != 404:
        print(f"[{s}] {path}")
    time.sleep(DELAY)

print()
print("=" * 80)
print("RINGKASAN AKHIR")
print("=" * 80)
print(f"\n✅ Emiten endpoints aktif ({len(active_emiten)}):")
for s in active_emiten:
    print(f"   /api/emiten/BBCA/{s}")
print(f"\n✅ Global endpoints aktif ({len(active_global)}):")
for p in active_global:
    print(f"   {p}")
print("\nPaste output ini ke chat untuk update data_fetcher.py")
