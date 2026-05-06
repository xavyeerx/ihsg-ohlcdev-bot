"""
Probe endpoint Advanced Analytics sebagai alternatif SM endpoints yang 404.
Tujuan: konfirmasi availability + struktur data untuk integrasi ke smart_money.py

Jalankan: python scripts/probe_advanced_endpoints.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
BASE    = f"https://{RAPIDAPI_HOST}"
DELAY   = 2.0

ENDPOINTS = [
    # --- Advanced (global, tidak perlu symbol) ---
    ("getWhaleTransactions",  "/api/advanced/whale-transactions",  {}, "Pengganti running-trade: transaksi besar"),
    ("getInsiderScreening",   "/api/advanced/insider-screening",   {}, "Pengganti all-insider-trading: screening insider"),
    ("getInsiderNetSummary",  "/api/advanced/insider-net-summary", {}, "Net insider per emiten"),
    ("getMultiMarketScreener","/api/advanced/multi-market-screener",{}, "Multi market screener"),
    ("getCorrelationMatrix",  "/api/advanced/correlation-matrix",  {}, "Korelasi antar saham"),
    ("getTechnicalAnalysis",  "/api/advanced/technical-analysis",  {"symbol": "BBCA"}, "TA per symbol"),

    # --- Bandarmology (global) ---
    ("getBandarDistribution", "/api/bandarmology/distribution",    {}, "Distribusi bandar"),
    ("getPumpDumpDetection",  "/api/bandarmology/pump-dump",        {}, "Pump dump detection"),
    ("getBandarAccumulation", "/api/bandarmology/accumulation",     {}, "Akumulasi bandar"),
    ("getSmartMoneyFlow",     "/api/bandarmology/smart-money-flow", {}, "Smart money flow"),

    # --- Market Sentiment ---
    ("getRetailBandarSentiment", "/api/market-sentiment/retail-bandar", {}, "Sentimen retail vs bandar"),

    # --- Emiten (per symbol) ---
    ("getInsiderTradingBySymbol", "/api/emiten/BBCA/insider-trading", {}, "Insider by symbol"),
    ("getOrderbook",              "/api/emiten/BBCA/orderbook",        {}, "Orderbook real-time"),
    ("getTradebookChart",         "/api/emiten/BBCA/tradebook-chart",  {}, "Tradebook chart"),
    ("getSeasonality",            "/api/emiten/BBCA/seasonality",      {}, "Seasonality pattern"),
    ("getHistoricalSummary",      "/api/emiten/BBCA/historical-summary",{}, "Historical broksum summary"),
    ("getSubsidiary",             "/api/emiten/BBCA/subsidiary",       {}, "Anak perusahaan"),
    ("getFundachartMetrics",      "/api/emiten/BBCA/fundachart-metrics",{}, "Fundamental metrics"),
    ("getStockInsights",          "/api/emiten/BBCA/insights",         {}, "BETA: stock insights"),
    ("getStockEarnings",          "/api/emiten/BBCA/earnings",         {}, "BETA: earnings"),
    ("getStockKeyRatios",         "/api/emiten/BBCA/key-ratios",       {}, "BETA: key ratios"),
]

print("=" * 90)
print("PROBE: Advanced Analytics & Emiten Endpoints")
print("=" * 90)

ok_list   = []
fail_list = []

for fname, path, params, note in ENDPOINTS:
    url = BASE + path
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        s = r.status_code
        try:    body = r.json()
        except: body = {"raw": r.text[:300]}

        icon = "✅" if s == 200 else ("🔒" if s == 403 else ("❌" if s == 404 else "⚠️"))
        print(f"\n{icon} [{s}] {fname}")
        print(f"     Path : {path}")
        print(f"     Note : {note}")

        if s == 200:
            ok_list.append(fname)
            if isinstance(body, dict):
                data = body.get("data", body)
                if isinstance(data, list):
                    print(f"     Data : list[{len(data)}] items")
                    if data and isinstance(data[0], dict):
                        print(f"     Keys : {list(data[0].keys())[:8]}")
                        # Tampilkan 1 sampel item
                        sample = {k: v for k, v in list(data[0].items())[:6]}
                        print(f"     Spl  : {json.dumps(sample, ensure_ascii=False)[:200]}")
                elif isinstance(data, dict):
                    print(f"     Keys : {list(data.keys())[:10]}")
                    sample = {k: str(v)[:40] for k, v in list(data.items())[:5]}
                    print(f"     Spl  : {json.dumps(sample, ensure_ascii=False)[:200]}")
            elif isinstance(body, list):
                print(f"     Data : list[{len(body)}] at root")
                if body and isinstance(body[0], dict):
                    print(f"     Keys : {list(body[0].keys())[:8]}")
        else:
            fail_list.append(fname)
            if isinstance(body, dict):
                msg = body.get("message", body.get("error", str(body)[:150]))
            else:
                msg = str(body)[:150]
            print(f"     Msg  : {msg}")

    except Exception as e:
        fail_list.append(fname)
        print(f"\nERR {fname}: {e}")

    time.sleep(DELAY)

print()
print("=" * 90)
print(f"✅ Available ({len(ok_list)}): {', '.join(ok_list)}")
print(f"❌ Unavailable ({len(fail_list)}): {', '.join(fail_list)}")
print()
print("REKOMENDASI INTEGRASI:")
print("  - getWhaleTransactions  → analisis whale/block trade (pengganti running-trade)")
print("  - getInsiderScreening   → screening insider (pengganti all-insider-trading)")
print("  - getBandarAccumulation → sinyal akumulasi bandar per saham")
print("  - getSmartMoneyFlow     → arus smart money masuk/keluar")
print("  - getHistoricalSummary  → riwayat broker summary per symbol")
