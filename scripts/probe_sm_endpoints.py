"""
Probe 3 Smart Money endpoints yang masih disabled (feature flag = False).
Tujuan: konfirmasi apakah 404 murni unavailable atau path salah.

Jalankan: python scripts/probe_sm_endpoints.py
Output: status, response body (untuk diagnosis), dan rekomendasi flag.
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}
BASE  = f"https://{RAPIDAPI_HOST}"
DELAY = 2.0

# Gunakan saham likuid supaya data paling mungkin ada
SYMBOLS = ["BBCA", "BBRI", "TLKM"]

ENDPOINTS_TO_PROBE = [
    # (nama_fungsi, path_template, keterangan)
    ("getRunningTrade",      "/api/emiten/{sym}/running-trade",       "Tesis 1: Whale / Block Trade"),
    ("getAllInsiderTrading",  "/api/emiten/{sym}/all-insider-trading", "Tesis 4: Insider"),
    ("getHoldingComposition","/api/emiten/{sym}/holding-composition", "Tesis 6: Konsentrasi"),
    # Bandingkan dengan endpoint yang sudah berfungsi:
    ("getForeignOwnership",  "/api/emiten/{sym}/foreign-ownership",   "KONTROL - sudah OK"),
    ("getInsiderTrading",    "/api/emiten/{sym}/insider-trading",      "insider by symbol (beda dg all-insider)"),
]

print("=" * 80)
print("PROBE: Smart Money Endpoints")
print("=" * 80)
print()

results = {}

for sym in SYMBOLS:
    print(f"\n{'─'*60}")
    print(f"  Symbol: {sym}")
    print(f"{'─'*60}")
    for fname, path_tpl, note in ENDPOINTS_TO_PROBE:
        path = path_tpl.format(sym=sym)
        url  = BASE + path
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            status = r.status_code
            try:
                body = r.json()
            except Exception:
                body = r.text[:300]

            icon = "✅" if status == 200 else ("🔒" if status == 403 else ("❌" if status == 404 else "⚠️"))
            print(f"\n  {icon} [{status}] {fname}")
            print(f"       Path : {path}")
            print(f"       Note : {note}")

            if status == 200:
                if isinstance(body, dict):
                    data_val = body.get("data", body)
                    if isinstance(data_val, list):
                        print(f"       Data : list[{len(data_val)}] items")
                        if data_val:
                            print(f"       Keys : {list(data_val[0].keys())[:6] if isinstance(data_val[0], dict) else str(data_val[0])[:80]}")
                    elif isinstance(data_val, dict):
                        print(f"       Keys : {list(data_val.keys())[:8]}")
                    else:
                        print(f"       Data : {str(data_val)[:120]}")
                elif isinstance(body, list):
                    print(f"       Data : list[{len(body)}] at root level")
                else:
                    print(f"       Body : {str(body)[:120]}")
                # simpan path yang berhasil
                results.setdefault(fname, {})["ok_path"] = path

            elif status == 404:
                # Tampilkan error message dari API
                if isinstance(body, dict):
                    msg = body.get("message", body.get("error", body.get("detail", str(body)[:200])))
                else:
                    msg = str(body)[:200]
                print(f"       Msg  : {msg}")

            elif status == 403:
                if isinstance(body, dict):
                    msg = body.get("message", str(body)[:200])
                else:
                    msg = str(body)[:200]
                print(f"       Msg  : {msg}")

        except Exception as e:
            print(f"\n  ERR {fname}: {e}")

        time.sleep(DELAY)

print()
print("=" * 80)
print("RINGKASAN & REKOMENDASI")
print("=" * 80)
print()
print("Berdasarkan hasil di atas, update config/settings.py:")
print()
print("  SM_RUNNING_TRADE_ENABLED     = True/False   # getRunningTrade")
print("  SM_INSIDER_TRADING_ENABLED   = True/False   # getAllInsiderTrading")
print("  SM_HOLDING_COMP_ENABLED      = True/False   # getHoldingComposition")
print()
print("Jika status 200 → set True (path sudah benar, hanya perlu enable)")
print("Jika status 404 → bisa jadi perlu plan upgrade atau endpoint belum aktif")
print("Jika status 403 → perlu upgrade plan RapidAPI")
print()
print("Setelah konfirmasi, jalankan: python run_evening.py")
