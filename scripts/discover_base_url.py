"""
Discover base URL dan prefix path yang benar dari API IDX RapidAPI.
Strategi: coba berbagai kombinasi base path + endpoint yang SUDAH TERBUKTI BERHASIL
untuk menemukan pola URL yang benar, lalu test endpoint yang 404.

Jalankan: python scripts/discover_base_url.py
"""
import sys, os, json, time, re
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
        except: body = {"raw": r.text[:200]}
        return r.status_code, body
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 80)
print("STEP 1: Konfirmasi endpoint yang PASTI BERHASIL dan lihat response header")
print("=" * 80)

# Endpoint yang sudah terbukti 200
known_ok = [
    ("/api/emiten/BBCA/foreign-ownership", {}),
    ("/api/chart/ohlcv", {"symbol": "BBCA"}),
    ("/api/main/idx-symbols", {}),
    ("/api/market-detector/broker-summary", {}),
]

for path, params in known_ok:
    try:
        r = requests.get(BASE + path, headers=HEADERS, params=params, timeout=15)
        print(f"[{r.status_code}] {path}")
        # Cetak semua response header untuk petunjuk
        for k, v in r.headers.items():
            if k.lower() in ("x-rapidapi-version", "x-api-version", "server", "via", "x-cache", "cf-ray"):
                print(f"       {k}: {v}")
    except Exception as e:
        print(f"ERR {path}: {e}")
    time.sleep(DELAY)

print()
print("=" * 80)
print("STEP 2: Coba berbagai prefix path untuk running-trade")
print("=" * 80)

# Variasi prefix yang mungkin
prefixes = [
    "",           # /api/emiten/BBCA/running-trade  (sudah dicoba, 404)
    "/v1",        # /v1/api/emiten/...
    "/v2",
    "/v3",
    "/ohlcdev",   # mungkin ada versi ohlcdev
    "/idx",
]

# Endpoint yang mau kita temukan path-nya
target_suffixes = [
    "/api/emiten/BBCA/running-trade",
    "/api/emiten/BBCA/all-insider-trading",
    "/api/emiten/BBCA/holding-composition",
    "/api/advanced/whale-transactions",
    "/api/bandarmology/accumulation",
]

for prefix in prefixes:
    for suffix in target_suffixes[:2]:  # test 2 saja untuk hemat quota
        path = prefix + suffix
        s, body = get(path)
        if s == 200:
            print(f"✅ FOUND! [{s}] {path}")
        elif s != 404:
            print(f"[{s}] {path} — {str(body)[:80]}")
    time.sleep(DELAY)

print()
print("=" * 80)
print("STEP 3: Probe root API untuk menemukan endpoint listing")
print("=" * 80)

# Banyak API punya endpoint discovery / docs
discovery_paths = [
    "/",
    "/api",
    "/api/",
    "/api/v1",
    "/docs",
    "/swagger",
    "/openapi.json",
    "/api/docs",
    "/api/endpoints",
    "/api/main/endpoints",
    "/api/main/info",
    "/api/info",
    "/api/status",
    "/api/health",
    "/api/main/morning-briefing",   # ini pasti ada, tapi lihat X-RapidAPI headers
]

for path in discovery_paths:
    s, body = get(path)
    if s == 200:
        if isinstance(body, dict):
            keys = list(body.keys())[:6]
            print(f"✅ [{s}] {path} — keys: {keys}")
        elif isinstance(body, list):
            print(f"✅ [{s}] {path} — list[{len(body)}]")
        else:
            print(f"✅ [{s}] {path} — {str(body)[:100]}")
    elif s not in (404, 0):
        print(f"[{s}] {path} — {str(body)[:80]}")
    time.sleep(0.8)

print()
print("=" * 80)
print("STEP 4: Test endpoint dari RapidAPI sidebar — coba nama endpoint persis")
print("=" * 80)

# Kadang RapidAPI pakai nama fungsi sebagai path
alt_paths = [
    ("/api/emiten/BBCA/runningTrade",        "camelCase"),
    ("/api/emiten/BBCA/running_trade",        "snake_case"),
    ("/api/emiten/BBCA/trade/running",        "nested"),
    ("/api/emiten/BBCA/trades",               "plural"),
    ("/api/running-trade",                    "no emiten prefix"),
    ("/api/running-trade/BBCA",               "symbol as param"),
    ("/api/emiten/running-trade/BBCA",        "reversed order"),
    ("/api/emiten/BBCA/all-insider",          "shortened"),
    ("/api/emiten/BBCA/insider",              "no all-"),
    ("/api/emiten/BBCA/insiders",             "plural"),
    ("/api/emiten/BBCA/holding",              "no -composition"),
    ("/api/emiten/BBCA/holdings",             "plural"),
    ("/api/emiten/BBCA/composition",          "no holding-"),
    ("/api/emiten/BBCA/shareholder",          "alt name"),
    ("/api/emiten/BBCA/shareholders",         "alt plural"),
    ("/api/emiten/BBCA/ownership",            "alt name"),
    ("/api/whale-transactions",               "no advanced prefix"),
    ("/api/whale-transactions/BBCA",          "with symbol"),
    ("/api/advanced/whale",                   "shortened"),
    ("/api/bandarmology/smart-money",         "no -flow"),
    ("/api/bandarmology/smart_money_flow",    "snake_case"),
    ("/api/bandarmology",                     "root bandarmology"),
]

found_any = False
for path, note in alt_paths:
    s, body = get(path)
    if s == 200:
        print(f"✅ FOUND [{s}] {path} ({note})")
        if isinstance(body, dict):
            print(f"   Keys: {list(body.keys())[:6]}")
        found_any = True
    elif s not in (404, 0):
        print(f"[{s}] {path} ({note}) — {str(body)[:60]}")
    time.sleep(0.8)

if not found_any:
    print("Tidak ada path alternatif yang berhasil (semua 404).")
    print()
    print("KESIMPULAN: Endpoint ini benar-benar tidak tersedia di plan ini.")
    print("Kemungkinan penyebab:")
    print("  1. Endpoint baru di sidebar RapidAPI tapi belum di-deploy oleh provider")
    print("  2. Butuh plan yang lebih tinggi dari ULTRA (enterprise/custom)")
    print("  3. Provider API membutuhkan approval/whitelist khusus")
    print()
    print("SOLUSI YANG DIREKOMENDASIKAN:")
    print("  → Hubungi provider langsung di RapidAPI (klik 'Contact Provider')")
    print("  → Tanyakan kapan endpoint running-trade, all-insider-trading,")
    print("     holding-composition, dan advanced/* akan aktif untuk plan ULTRA")
