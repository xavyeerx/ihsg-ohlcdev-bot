#!/usr/bin/env python3
"""
TEST ENDPOINTS -- Cek aksesibilitas semua endpoint
Jalankan: python scripts/test_endpoints.py

Output: status setiap endpoint + sample response jika berhasil
"""

import sys, os, json, requests, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

SYMBOL  = "BBCA"
HEADERS = {
    "X-RapidAPI-Key":  RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}
BASE = f"https://{RAPIDAPI_HOST}"

def test(label, path, params=None):
    """Hit endpoint, print status + preview response."""
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, headers=HEADERS, params=params or {}, timeout=15)
        status = r.status_code
        if status == 200:
            try:
                data = r.json()
                # Ambil preview: keys top-level + ukuran data
                if isinstance(data, dict):
                    keys = list(data.keys())
                    preview = f"keys={keys[:6]}"
                    # Coba ambil satu nilai menarik
                    for k in ("data", "result", "records"):
                        if k in data:
                            inner = data[k]
                            if isinstance(inner, list):
                                preview += f" | list[{len(inner)}] item"
                                if len(inner) > 0:
                                    first = inner[0]
                                    if isinstance(first, dict):
                                        preview += f" | first keys={list(first.keys())[:5]}"
                            elif isinstance(inner, dict):
                                preview += f" | inner keys={list(inner.keys())[:5]}"
                            break
                elif isinstance(data, list):
                    preview = f"list[{len(data)}]"
                    if len(data) > 0 and isinstance(data[0], dict):
                        preview += f" | first keys={list(data[0].keys())[:5]}"
                else:
                    preview = str(data)[:100]
                print(f"  [OK ]  {label}")
                print(f"         {preview}")
            except Exception as e:
                print(f"  [OK ]  {label}  (response bukan JSON: {e})")
        elif status == 404:
            print(f"  [404]  {label}  -- TIDAK TERSEDIA")
        elif status == 403:
            print(f"  [403]  {label}  -- FORBIDDEN (plan tidak support)")
        elif status == 429:
            print(f"  [429]  {label}  -- RATE LIMITED")
        else:
            print(f"  [{status}]  {label}  -- {r.text[:80]}")
    except requests.exceptions.Timeout:
        print(f"  [---]  {label}  -- TIMEOUT")
    except Exception as e:
        print(f"  [ERR]  {label}  -- {e}")
    time.sleep(0.5)  # jaga rate limit

print("=" * 60)
print("  IDX Market Intelligence — Endpoint Access Test")
print(f"  Symbol: {SYMBOL}  |  Plan: ULTRA")
print("=" * 60)

# ── Main / Market ────────────────────────────────────────────
print("\n[MAIN / MARKET]")
test("getTrendingStocks",    "/api/main/trending")
test("getIdxSymbols",        "/api/main/symbols")
test("getMorningBriefing",   "/api/main/morning-briefing")
test("getForexIdrImpact",    "/api/main/forex-idr-impact")
test("getCommoditiesImpact", "/api/main/commodities-impact")
test("getGlobalMarketOverview",  "/api/main/global-market")
test("getGlobalImpactAnalysis",  "/api/main/global-impact")

# ── Sectors ──────────────────────────────────────────────────
print("\n[SECTORS]")
test("getAllSectors",        "/api/sector/all")
test("getSubSectors",        "/api/sector/subsectors")
test("getSectorCompanies",   "/api/sector/companies",      {"sector": "Finance"})
test("getSectorCorrelation", "/api/sector/correlation")
test("getSectorRotation",    "/api/sector/rotation")

# ── Calendar / Corporate Actions ─────────────────────────────
print("\n[CALENDAR / CORPORATE ACTIONS]")
test("getDividendCalendar",       "/api/calendar/dividend")
test("getStockSplitCalendar",     "/api/calendar/stock-split")
test("getRightIssueCalendar",     "/api/calendar/right-issue")
test("getTodayCorporateActions",  "/api/calendar/corporate-actions/today")
test("getIpoCalendar",            "/api/calendar/ipo")
test("getWarrantCalendar",        "/api/calendar/warrant")
test("getBonusCalendar",          "/api/calendar/bonus")
test("getRupsCalendar",           "/api/calendar/rups")
test("getTenderOfferCalendar",    "/api/calendar/tender-offer")
test("getEconomicCalendar",       "/api/calendar/economic")

# ── Emiten (per saham) ────────────────────────────────────────
print(f"\n[EMITEN — {SYMBOL}]")
test("getEmitenInfo",              f"/api/emiten/{SYMBOL}/info")
test("getForeignOwnership",        f"/api/emiten/{SYMBOL}/foreign-ownership")
test("getInsiderTradingBySymbol",  f"/api/emiten/{SYMBOL}/insider-trading")
test("getHoldingComposition",      f"/api/emiten/{SYMBOL}/holding-composition")
test("getSeasonality",             f"/api/emiten/{SYMBOL}/seasonality")
test("getFinancials",              f"/api/emiten/{SYMBOL}/financials")
test("getKeystats",                f"/api/emiten/{SYMBOL}/keystats")
test("getHistoricalSummary",       f"/api/emiten/{SYMBOL}/historical-summary")
test("getOrderbook",               f"/api/emiten/{SYMBOL}/orderbook")
test("getRunningTrade",            f"/api/emiten/{SYMBOL}/running-trade")
test("getSubsidiary",              f"/api/emiten/{SYMBOL}/subsidiary")
test("getProfileBackground",       f"/api/emiten/{SYMBOL}/profile")
test("getFundachart",              f"/api/emiten/{SYMBOL}/fundachart")
test("getFundachartMetrics",       f"/api/emiten/{SYMBOL}/fundachart-metrics")
test("getTradebookChart",          f"/api/emiten/{SYMBOL}/tradebook-chart")
test("getBrokerTradeChart",        f"/api/emiten/{SYMBOL}/broker-trade-chart")
test("getAllInsiderTrading",        f"/api/emiten/{SYMBOL}/all-insider-trading")

# ── Retail Opportunity ────────────────────────────────────────
print("\n[RETAIL OPPORTUNITY]")
test("getBreakoutAlerts",    "/api/retail/breakout-alerts")
test("scanMultibagger",      "/api/retail/multibagger")
test("calculateRiskReward",  f"/api/retail/risk-reward/{SYMBOL}")

# ── Market Sentiment ──────────────────────────────────────────
print("\n[MARKET SENTIMENT]")
test("getRetailBandarSentiment", "/api/sentiment/retail-bandar")
test("getIpoMomentum",           "/api/sentiment/ipo-momentum")

# ── Advanced Analytics ────────────────────────────────────────
print("\n[ADVANCED ANALYTICS]")
test("getInsiderScreening",   "/api/analytics/insider-screening")
test("getMultiMarketScreener","/api/analytics/multi-market-screener")
test("getCorrelationMatrix",  "/api/analytics/correlation-matrix")
test("getWhaleTransactions",  "/api/analytics/whale-transactions")
test("getTechnicalAnalysis",  f"/api/analytics/technical/{SYMBOL}")
test("getInsiderNetSummary",  "/api/analytics/insider-net-summary")

# ── BETA ──────────────────────────────────────────────────────
print("\n[BETA]")
test("getStockKeyRatios", f"/api/beta/key-ratios/{SYMBOL}")
test("getStockInsights",  f"/api/beta/insights/{SYMBOL}")
test("getStockEarnings",  f"/api/beta/earnings/{SYMBOL}")
test("getStockEquities",  f"/api/beta/equities/{SYMBOL}")

# ── Market Detector (konfirmasi 404) ──────────────────────────
print("\n[MARKET DETECTOR]")
test("getBrokerSummary",   f"/api/broker/summary/{SYMBOL}")
test("getTopBrokers",      f"/api/broker/top/{SYMBOL}")
test("getMarketMover",     "/api/main/movers")

print("\n" + "=" * 60)
print("  Test selesai.")
print("  [OK] = accessible | [404] = tidak tersedia | [403] = forbidden")
print("=" * 60)
