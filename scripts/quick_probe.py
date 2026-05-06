"""Jalankan: python scripts/quick_probe.py"""
import sys, os, time, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

H = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
B = f"https://{RAPIDAPI_HOST}"
SYM = "BBCA"

tests = [
    # SM endpoints — query param style
    ("/api/emiten/all-insider-trading",      {"symbol": SYM}),
    ("/api/emiten/holding-composition",      {"symbol": SYM}),
    ("/api/emiten/foreign-ownership",        {"symbol": SYM}),
    ("/api/emiten/historical-summary",       {"symbol": SYM}),
    ("/api/emiten/broker-summary",           {"symbol": SYM}),
    ("/api/emiten/info",                     {"symbol": SYM}),
    ("/api/emiten/financials",               {"symbol": SYM}),
    ("/api/emiten/keystats",                 {"symbol": SYM}),
    ("/api/emiten/orderbook",                {"symbol": SYM}),
    # OHLCV & market data — yang tiba-tiba 404
    ("/api/chart/ohlcv",                     {"symbol": SYM}),
    ("/api/chart/latest-ohlcv",              {"symbol": SYM}),
    ("/api/emiten/ohlcv",                    {"symbol": SYM}),
    # Market detector — broker summary global
    ("/api/market-detector/broker-summary",  {}),
    ("/api/market-detector/broker-summary",  {"symbol": SYM}),
    ("/api/market-detector/top-brokers",     {}),
    ("/api/market-detector/top-stocks",      {}),
    # Main
    ("/api/main/idx-symbols",                {}),
    ("/api/main/trending-stocks",            {}),
    # Bandarmology
    ("/api/bandarmology/accumulation",       {}),
    ("/api/bandarmology/smart-money-flow",   {}),
    # Advanced
    ("/api/advanced/whale-transactions",     {}),
    ("/api/advanced/insider-screening",      {}),
    # Retail
    ("/api/retail-opportunity/breakout-alerts", {}),
    ("/api/market-sentiment/retail-bandar",  {}),
    ("/api/global-market/overview",          {}),
]

for path, params in tests:
    try:
        r = requests.get(B + path, headers=H, params=params, timeout=10)
        s = r.status_code
        icon = "✅" if s == 200 else ("⚠️" if s not in (404,) else "❌")
        param_str = "?" + "&".join(f"{k}={v}" for k,v in params.items()) if params else ""
        print(f"{icon} [{s}] {path}{param_str}")
    except Exception as e:
        print(f"ERR {path}: {e}")
    time.sleep(0.5)
