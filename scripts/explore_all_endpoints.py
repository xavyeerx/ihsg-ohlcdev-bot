"""
Test semua endpoint yang ada di sidebar RapidAPI IDX.
Jalankan: python scripts/explore_all_endpoints.py
Delay 2 detik antar request.
"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
BASE    = f"https://{RAPIDAPI_HOST}"
DELAY   = 2.0

# Semua endpoint dari sidebar — format: (nama, path, params)
ENDPOINTS = [
    # Calendar
    ("getTenderOfferCalendar",    "/api/calendar/tender-offer",       {}),
    ("getRightIssueCalendar",     "/api/calendar/right-issue",        {}),
    ("getIpoCalendar",            "/api/calendar/ipo",                {}),
    ("getEconomicCalendar",       "/api/calendar/economic",           {}),
    ("getStockSplitCalendar",     "/api/calendar/stock-split",        {}),
    ("getWarrantCalendar",        "/api/calendar/warrant",            {}),
    ("getDividendCalendar",       "/api/calendar/dividend",           {}),
    ("getRupsCalendar",           "/api/calendar/rups",               {}),
    ("getTodayCorporateActions",  "/api/calendar/corporate-actions",  {}),
    ("getBonusCalendar",          "/api/calendar/bonus",              {}),

    # Main
    ("getMorningBriefing",        "/api/main/morning-briefing",       {}),
    ("searchStocks",              "/api/main/search-stocks",          {"q": "BBCA"}),
    ("getUsStocksParent",         "/api/main/us-stocks-parent",       {}),
    ("getTrendingStocks",         "/api/main/trending-stocks",        {}),
    ("getBrokerCodes",            "/api/main/broker-codes",           {}),
    ("getIdxSymbols",             "/api/main/idx-symbols",            {}),
    ("getCommoditiesImpact",      "/api/main/commodities-impact",     {}),
    ("getForexIdrImpact",         "/api/main/forex-idr-impact",       {}),

    # Global Market
    ("getGlobalImpactAnalysis",   "/api/global-market/impact-analysis",  {}),
    ("getGlobalMarketOverview",   "/api/global-market/overview",         {}),
    ("getIndicesImpact",          "/api/global-market/indices-impact",   {}),

    # Chart
    ("getLatestOHLCV",            "/api/chart/latest-ohlcv",          {"symbol": "BBCA"}),
    ("getOHLCV",                  "/api/chart/ohlcv",                 {"symbol": "BBCA"}),

    # Sectors
    ("getAllSectors",             "/api/sectors/all",                 {}),
    ("getSubSectors",             "/api/sectors/sub-sectors",         {}),
    ("getSectorCorrelation",      "/api/sectors/correlation",         {}),
    ("getSectorCompanies",        "/api/sectors/companies",           {"sector": "banking"}),

    # Movers
    ("getMarketMover",            "/api/movers/market",               {}),

    # Market Detector
    ("getBrokerSummary",          "/api/market-detector/broker-summary",   {}),
    ("getTopBrokers",             "/api/market-detector/top-brokers",      {}),
    ("getTopStocks",              "/api/market-detector/top-stocks",       {}),
    ("getBrokerActivity",         "/api/market-detector/broker-activity",  {}),

    # Bandarmology
    ("getBandarDistribution",     "/api/bandarmology/distribution",        {}),
    ("getPumpDumpDetection",      "/api/bandarmology/pump-dump",           {}),
    ("getBandarAccumulation",     "/api/bandarmology/accumulation",        {}),
    ("getSmartMoneyFlow",         "/api/bandarmology/smart-money-flow",    {}),

    # Retail Opportunity
    ("getSectorRotation",         "/api/retail-opportunity/sector-rotation",  {}),
    ("scanMultibagger",           "/api/retail-opportunity/multibagger",      {}),
    ("getBreakoutAlerts",         "/api/retail-opportunity/breakout-alerts",  {}),
    ("calculateRiskReward",       "/api/retail-opportunity/risk-reward",      {"symbol": "BBCA"}),

    # Market Sentiment
    ("getRetailBandarSentiment",  "/api/market-sentiment/retail-bandar",   {}),
    ("getIpoMomentum",            "/api/market-sentiment/ipo-momentum",    {}),

    # Advanced Analytics
    ("getInsiderScreening",       "/api/advanced/insider-screening",       {}),
    ("getMultiMarketScreener",    "/api/advanced/multi-market-screener",   {}),
    ("getCorrelationMatrix",      "/api/advanced/correlation-matrix",      {}),
    ("getWhaleTransactions",      "/api/advanced/whale-transactions",      {}),
    ("getTechnicalAnalysis",      "/api/advanced/technical-analysis",      {"symbol": "BBCA"}),
    ("getInsiderNetSummary",      "/api/advanced/insider-net-summary",     {}),

    # Emiten
    ("getForeignOwnership",       "/api/emiten/BBCA/foreign-ownership",    {}),
    ("getOrderbook",              "/api/emiten/BBCA/orderbook",            {}),
    ("getInsiderTradingBySymbol", "/api/emiten/BBCA/insider-trading",      {}),
    ("getSeasonality",            "/api/emiten/BBCA/seasonality",          {}),
    ("getHoldingComposition",     "/api/emiten/BBCA/holding-composition",  {}),
    ("getHistoricalSummary",      "/api/emiten/BBCA/historical-summary",   {}),
    ("getFinancials",             "/api/emiten/BBCA/financials",           {}),
    ("getKeystats",               "/api/emiten/BBCA/keystats",             {}),
    ("getTradebookChart",         "/api/emiten/BBCA/tradebook-chart",      {}),
    ("getBrokerTradeChart",       "/api/emiten/BBCA/broker-trade-chart",   {}),
    ("getAllInsiderTrading",       "/api/emiten/BBCA/all-insider-trading",  {}),
    ("getRunningTrade",           "/api/emiten/BBCA/running-trade",        {}),
    ("getSubsidiary",             "/api/emiten/BBCA/subsidiary",           {}),
    ("getEmitenInfo",             "/api/emiten/BBCA/info",                 {}),
    ("getProfileBackground",      "/api/emiten/BBCA/profile-background",   {}),
    ("getFundachartMetrics",      "/api/emiten/BBCA/fundachart-metrics",   {}),
    ("getFundachart",             "/api/emiten/BBCA/fundachart",           {}),

    # BETA
    ("getStockKeyRatios",         "/api/emiten/BBCA/key-ratios",           {}),
    ("getStockInsights",          "/api/emiten/BBCA/insights",             {}),
    ("getStockEarnings",          "/api/emiten/BBCA/earnings",             {}),
]

print(f"{'Status':<4} {'Endpoint':<30} {'Path':<50} Note")
print("-" * 110)

ok_list   = []
fail_list = []

for name, path, params in ENDPOINTS:
    try:
        r = requests.get(BASE + path, headers=HEADERS, params=params, timeout=15)
        s = r.status_code
        if s == 200:
            try:
                data = r.json()
                inner = data.get("data", data) if isinstance(data, dict) else data
                if isinstance(inner, dict):   note = str(list(inner.keys())[:4])
                elif isinstance(inner, list): note = f"list[{len(inner)}]"
                else:                         note = str(inner)[:40]
            except:
                note = r.text[:40]
            print(f"✅   {name:<30} {path:<50} {note}")
            ok_list.append((name, path))
        elif s == 403:
            print(f"🔒   {name:<30} {path:<50} Forbidden (upgrade plan)")
            fail_list.append((name, "403"))
        elif s == 404:
            print(f"❌   {name:<30} {path:<50} Not Found")
            fail_list.append((name, "404"))
        elif s == 429:
            print(f"⚠️    {name:<30} {path:<50} Rate Limited")
            fail_list.append((name, "429"))
        else:
            print(f"??   {name:<30} {path:<50} {s} {r.text[:30]}")
            fail_list.append((name, str(s)))
    except Exception as e:
        print(f"ERR  {name:<30} {path:<50} {e}")
        fail_list.append((name, "ERR"))
    time.sleep(DELAY)

print("\n" + "=" * 60)
print(f"✅ Available : {len(ok_list)}")
print(f"❌ Not Found : {sum(1 for _,s in fail_list if s=='404')}")
print(f"🔒 Forbidden : {sum(1 for _,s in fail_list if s=='403')}")
print(f"⚠️  Rate Limit: {sum(1 for _,s in fail_list if s=='429')}")
