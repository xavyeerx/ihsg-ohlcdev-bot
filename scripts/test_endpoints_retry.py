#!/usr/bin/env python3
"""
TEST ENDPOINTS RETRY -- Khusus endpoint yang kena 429 tadi
Jeda lebih panjang antar request agar tidak rate limited
Jalankan: python scripts/test_endpoints_retry.py
"""

import sys, os, json, requests, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

SYMBOL  = "BBCA"
HEADERS = {
    "X-RapidAPI-Key":  RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}
BASE  = f"https://{RAPIDAPI_HOST}"
DELAY = 3  # detik antar request

def test(label, path, params=None, show_sample=True):
    url = f"{BASE}{path}"
    print(f"\n  Testing: {label}")
    print(f"  URL    : {path}")
    try:
        r = requests.get(url, headers=HEADERS, params=params or {}, timeout=15)
        status = r.status_code
        if status == 200:
            try:
                data = r.json()
                print(f"  Status : OK (200)")
                # Tampilkan sample data lebih detail
                def show(obj, indent=0, max_depth=2, max_keys=6):
                    pad = "  " * (indent + 2)
                    if indent >= max_depth:
                        print(f"{pad}...")
                        return
                    if isinstance(obj, dict):
                        for i, (k, v) in enumerate(obj.items()):
                            if i >= max_keys:
                                print(f"{pad}... (+{len(obj)-max_keys} more keys)")
                                break
                            if isinstance(v, (dict, list)):
                                size = f"[{len(v)} items]" if isinstance(v, list) else f"{{...}}"
                                print(f"{pad}{k}: {size}")
                                if indent < max_depth - 1:
                                    show(v, indent+1, max_depth, max_keys)
                            else:
                                val = str(v)[:60]
                                print(f"{pad}{k}: {val}")
                    elif isinstance(obj, list):
                        print(f"{pad}[{len(obj)} items]")
                        if len(obj) > 0:
                            print(f"{pad}First item:")
                            show(obj[0], indent+1, max_depth, max_keys)
                if show_sample:
                    print(f"  Data   :")
                    show(data)
            except Exception as e:
                print(f"  Status : OK (200) — bukan JSON: {e}")
                print(f"  Raw    : {r.text[:150]}")
        elif status == 404:
            print(f"  Status : 404 — TIDAK TERSEDIA")
        elif status == 403:
            print(f"  Status : 403 — FORBIDDEN")
        elif status == 429:
            print(f"  Status : 429 — MASIH RATE LIMITED, coba lagi nanti")
        elif status == 400:
            print(f"  Status : 400 — Parameter kurang/salah: {r.text[:100]}")
        elif status == 500:
            print(f"  Status : 500 — Server error: {r.text[:100]}")
        else:
            print(f"  Status : {status} — {r.text[:100]}")
    except requests.exceptions.Timeout:
        print(f"  Status : TIMEOUT")
    except Exception as e:
        print(f"  Status : ERROR — {e}")
    print(f"  {'─'*50}")
    time.sleep(DELAY)

print("=" * 60)
print("  Retry Test — Endpoint yang sebelumnya 429")
print(f"  Symbol: {SYMBOL} | Jeda: {DELAY}s antar request")
print("=" * 60)

print("\n[MAIN / MARKET]")
test("getMorningBriefing",    "/api/main/morning-briefing")
test("getGlobalImpactAnalysis", "/api/main/global-impact")

print("\n[SECTORS]")
test("getSectorCorrelation",  "/api/sector/correlation")

print("\n[CALENDAR]")
test("getDividendCalendar",   "/api/calendar/dividend")
test("getRightIssueCalendar", "/api/calendar/right-issue")
test("getIpoCalendar",        "/api/calendar/ipo")

print("\n[EMITEN]")
test("getKeystats",           f"/api/emiten/{SYMBOL}/keystats")
test("getSubsidiary",         f"/api/emiten/{SYMBOL}/subsidiary")
test("getBrokerTradeChart",   f"/api/emiten/{SYMBOL}/broker-trade-chart")

print("\n[RETAIL OPPORTUNITY]")
test("getBreakoutAlerts",     "/api/retail/breakout-alerts")

print("\n[MARKET SENTIMENT]")
test("getIpoMomentum",        "/api/sentiment/ipo-momentum")

print("\n[ADVANCED ANALYTICS]")
test("getMultiMarketScreener","/api/analytics/multi-market-screener")
test("getWhaleTransactions",  "/api/analytics/whale-transactions")
test("getInsiderNetSummary",  "/api/analytics/insider-net-summary")

print("\n[BETA]")
test("getStockInsights",      f"/api/beta/insights/{SYMBOL}")

print("\n[MARKET DETECTOR]")
test("getTopBrokers",         f"/api/broker/top/{SYMBOL}")

print("\n" + "=" * 60)
print("  Retry selesai.")
print("=" * 60)
