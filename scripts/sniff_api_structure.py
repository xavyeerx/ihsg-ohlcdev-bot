"""
Sniff struktur API dari response yang sudah berhasil.
Tujuan: temukan apakah ada hint path, versi, atau endpoint lain di dalam response.

Jalankan: python scripts/sniff_api_structure.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
from config.settings import RAPIDAPI_KEY, RAPIDAPI_HOST

HEADERS = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
BASE    = f"https://{RAPIDAPI_HOST}"

def req(path, params=None):
    try:
        r = requests.get(BASE + path, headers=HEADERS, params=params or {}, timeout=15)
        return r
    except Exception as e:
        print(f"ERR {path}: {e}")
        return None

# ── 1. Cetak SEMUA response header dari endpoint yang berhasil ──────────────
print("=" * 80)
print("1. RESPONSE HEADERS (dari /api/emiten/BBCA/foreign-ownership)")
print("=" * 80)
r = req("/api/emiten/BBCA/foreign-ownership")
if r:
    print(f"Status: {r.status_code}")
    for k, v in sorted(r.headers.items()):
        print(f"  {k}: {v}")

time.sleep(2)

# ── 2. Cek apakah ada "x-rapidapi-region" atau version hint ─────────────────
print()
print("=" * 80)
print("2. RESPONSE HEADERS (dari /api/chart/ohlcv)")
print("=" * 80)
r2 = req("/api/chart/ohlcv", {"symbol": "BBCA"})
if r2:
    for k, v in sorted(r2.headers.items()):
        print(f"  {k}: {v}")

time.sleep(2)

# ── 3. Baca isi morning-briefing — mungkin ada link/referensi endpoint ───────
print()
print("=" * 80)
print("3. MORNING BRIEFING response (cari clue endpoint)")
print("=" * 80)
r3 = req("/api/main/morning-briefing")
if r3 and r3.status_code == 200:
    body = r3.json()
    print(json.dumps(body, indent=2, ensure_ascii=False)[:3000])

time.sleep(2)

# ── 4. Coba endpoint yang ADA di respons getIdxSymbols untuk lihat format ────
print()
print("=" * 80)
print("4. IDX SYMBOLS — struktur data (apakah ada field endpoint/link?)")
print("=" * 80)
r4 = req("/api/main/idx-symbols")
if r4 and r4.status_code == 200:
    body = r4.json()
    if isinstance(body, dict):
        print("Top-level keys:", list(body.keys()))
        data = body.get("data", body)
        if isinstance(data, list) and data:
            print(f"Total symbols: {len(data)}")
            print("Sample item:", json.dumps(data[0], ensure_ascii=False))
            print("Sample item 2:", json.dumps(data[1], ensure_ascii=False))

time.sleep(2)

# ── 5. Coba /api/emiten/BBCA tanpa suffix — mungkin ada response daftar endpoint
print()
print("=" * 80)
print("5. EMITEN ROOT: /api/emiten/BBCA (tanpa suffix)")
print("=" * 80)
r5 = req("/api/emiten/BBCA")
if r5:
    print(f"Status: {r5.status_code}")
    try:
        body = r5.json()
        print(json.dumps(body, indent=2, ensure_ascii=False)[:2000])
    except:
        print(r5.text[:500])

time.sleep(2)

# ── 6. Coba /api/emiten tanpa symbol
print()
print("=" * 80)
print("6. EMITEN ROOT: /api/emiten (tanpa symbol)")
print("=" * 80)
r6 = req("/api/emiten")
if r6:
    print(f"Status: {r6.status_code}")
    try:
        body = r6.json()
        print(json.dumps(body, indent=2, ensure_ascii=False)[:2000])
    except:
        print(r6.text[:500])

time.sleep(2)

# ── 7. Coba broker-summary dengan parameter berbeda untuk cari clue
print()
print("=" * 80)
print("7. BROKER SUMMARY full response (lihat struktur + metadata)")
print("=" * 80)
r7 = req("/api/market-detector/broker-summary")
if r7 and r7.status_code == 200:
    body = r7.json()
    if isinstance(body, dict):
        print("Top-level keys:", list(body.keys()))
        # Cek ada metadata/links di body
        for k in ("meta", "links", "endpoints", "_links", "version", "api_version"):
            if k in body:
                print(f"Found '{k}':", body[k])
        data = body.get("data", [])
        if isinstance(data, list) and data:
            print(f"\nData length: {len(data)}")
            print("Sample:", json.dumps(data[0] if data else {}, ensure_ascii=False)[:300])

time.sleep(2)

# ── 8. Test dengan lowercase symbol
print()
print("=" * 80)
print("8. LOWERCASE SYMBOL TEST: /api/emiten/bbca/running-trade")
print("=" * 80)
for sym in ["bbca", "BBCA"]:
    for ep in ["running-trade", "all-insider-trading", "holding-composition"]:
        path = f"/api/emiten/{sym}/{ep}"
        r = req(path)
        if r:
            s = r.status_code
            if s != 404:
                print(f"[{s}] {path}")
                try: print(r.json())
                except: print(r.text[:200])
            else:
                try:
                    msg = r.json().get("message", "404")
                except:
                    msg = "404"
                print(f"[404] {path} — {msg[:60]}")
        time.sleep(1)

# ── 9. Coba dengan query param ?symbol= bukannya path param
print()
print("=" * 80)
print("9. QUERY PARAM STYLE: /api/running-trade?symbol=BBCA")
print("=" * 80)
alt_styles = [
    ("/api/running-trade",              {"symbol": "BBCA"}),
    ("/api/all-insider-trading",        {"symbol": "BBCA"}),
    ("/api/holding-composition",        {"symbol": "BBCA"}),
    ("/api/emiten/running-trade",       {"symbol": "BBCA"}),
    ("/api/emiten/all-insider-trading", {"symbol": "BBCA"}),
    ("/api/emiten/holding-composition", {"symbol": "BBCA"}),
    ("/api/advanced/running-trade",     {"symbol": "BBCA"}),
    ("/api/advanced/insider-trading",   {"symbol": "BBCA"}),
    ("/api/advanced/holding",           {"symbol": "BBCA"}),
]
for path, params in alt_styles:
    r = req(path, params)
    if r and r.status_code != 404:
        print(f"✅ [{r.status_code}] {path} params={params}")
        try: print(json.dumps(r.json(), ensure_ascii=False)[:300])
        except: print(r.text[:200])
    else:
        print(f"[404] {path}")
    time.sleep(1)

print()
print("=" * 80)
print("SELESAI — Paste output ini ke chat untuk analisis lebih lanjut.")
