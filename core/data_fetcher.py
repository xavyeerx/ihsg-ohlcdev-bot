# DATA FETCHER -- IDX Market Intelligence API (Market Reaper via RapidAPI)
#
# Endpoint tersedia (plan ULTRA):
#   OHLCV     : GET /api/chart/{symbol}/{interval}/latest?limit=N
#               Response: {success, data: {message, data: {allow_decimal, chartbit: [...]}}}
#               interval: "daily","1m","5m","15m","30m","1h","2h","3h","4h"
#   Stock Info: GET /api/emiten/{symbol}/info
#   Broker Summary: GET /api/market-detector/broker-summary/{symbol}
#   Top Brokers   : GET /api/broker/top/{symbol}
#   Market Movers : GET /api/main/movers
#   Bandarmology  : GET /api/bandarmology/*

import time
import logging
import requests
from requests.adapters import HTTPAdapter
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import (
    RAPIDAPI_KEY, RAPIDAPI_HOST,
    OHLCV_INTERVAL, OHLCV_BARS,
    REQUEST_TIMEOUT, MAX_RETRIES, RATE_LIMIT_DELAY
)

logger = logging.getLogger(__name__)

BASE_URL = f"https://{RAPIDAPI_HOST}"
HEADERS  = {
    "X-RapidAPI-Key":  RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}

# Satu Session + pool TCP untuk ribuan request paralel (lebih cepat dari requests.get tiap kali).
_HTTP_SESSION: Optional[requests.Session] = None


def _http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.mount(
            "https://",
            HTTPAdapter(pool_connections=128, pool_maxsize=128, max_retries=0),
        )
        _HTTP_SESSION = s
    return _HTTP_SESSION


# ---------------------------------------------------------------
# Helper: HTTP GET dengan retry + rate limit guard
# ---------------------------------------------------------------
def _get(endpoint: str, params: dict = None) -> Optional[Any]:
    url = f"{BASE_URL}{endpoint}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = _http_session().get(url, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning(f"Rate limit [{endpoint}], tunggu 5 detik...")
                time.sleep(5)
            else:
                logger.warning(f"HTTP {resp.status_code} pada {endpoint}: {resp.text[:150]}")
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout [{attempt}/{MAX_RETRIES}] {endpoint}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error {endpoint}: {e}")
            return None
        if RATE_LIMIT_DELAY and RATE_LIMIT_DELAY > 0:
            time.sleep(RATE_LIMIT_DELAY * attempt)
    logger.error(f"Gagal fetch {endpoint} setelah {MAX_RETRIES} percobaan")
    return None


# ---------------------------------------------------------------
# Helper: Cari list candle secara rekursif dalam nested dict/list
# Response OHLCV punya struktur 3 level:
#   root -> data -> data -> chartbit: [...]
# ---------------------------------------------------------------
def _extract_candles(obj, depth=0):
    if depth > 6:
        return None
    # Jika sudah list of dict dan punya key harga -> ini canlde array
    if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
        price_keys = {"open", "high", "low", "close", "o", "h", "l", "c"}
        if price_keys & set(obj[0].keys()):
            return obj
    if isinstance(obj, dict):
        # Cek key prioritas dulu (chartbit adalah key aktual dari API)
        for key in ("chartbit", "candles", "chart", "ohlcv", "bars", "data", "result"):
            if key in obj:
                found = _extract_candles(obj[key], depth + 1)
                if found is not None:
                    return found
    return None


# ---------------------------------------------------------------
# 1. OHLCV -- Candle intraday
# ---------------------------------------------------------------
def fetch_ohlcv(symbol: str, interval: str = OHLCV_INTERVAL, limit: int = OHLCV_BARS) -> Optional[pd.DataFrame]:
    """Fetch candle OHLCV dari IDX Market Intelligence API."""
    data = _get(f"/api/chart/{symbol}/{interval}/latest", params={"limit": limit})
    if not data:
        return None

    candles = _extract_candles(data)

    if not candles:
        logger.warning(f"[{symbol}] Format OHLCV tidak dikenali: {str(data)[:300]}")
        return None

    try:
        df = pd.DataFrame(candles)

        # Normalisasi nama kolom (API sudah pakai open/high/low/close lowercase)
        col_map = {
            "t": "datetime", "time": "datetime", "timestamp": "datetime",
            "o": "open",  "Open": "open",
            "h": "high",  "High": "high",
            "l": "low",   "Low":  "low",
            "c": "close", "Close": "close",
            "v": "volume", "Volume": "volume",
            # Daily OHLCV: nama kolom tanpa underscore
            "foreignbuy":  "foreign_buy",
            "foreignsell": "foreign_sell",
            "foreignflow": "foreign_flow",
            "freq_analyzer": "freq_analyzer",
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        required = ["open", "high", "low", "close", "volume"]
        missing  = [c for c in required if c not in df.columns]
        if missing:
            logger.warning(f"[{symbol}] Kolom OHLCV missing: {missing}. Kolom ada: {list(df.columns)}")
            return None

        df[required] = df[required].apply(pd.to_numeric, errors="coerce")
        df.dropna(subset=required, inplace=True)

        # Buat kolom datetime.
        # Untuk interval daily, prioritaskan kolom `date` dari API agar tidak
        # bergeser hari karena konversi unix UTC -> lokal.
        # Tangani kasus: (1) kolom duplikat, (2) unit detik vs milidetik
        dt_col = None
        if interval == "daily" and "date" in df.columns:
            # date biasanya format YYYY-MM-DD (hari bursa lokal/WIB)
            raw_date = df["date"]
            if hasattr(raw_date, "iloc") and raw_date.ndim > 1:
                raw_date = raw_date.iloc[:, 0]
            dt_col = pd.to_datetime(raw_date, errors="coerce")

        for src in ("unix_timestamp", "unixdate", "datetime", "date", "timestamp", "time", "t"):
            if dt_col is not None:
                break
            if src in df.columns:
                raw = df[src]
                # Jika kolom duplikat (DataFrame returns DataFrame), ambil kolom pertama
                if hasattr(raw, "iloc") and raw.ndim > 1:
                    raw = raw.iloc[:, 0]
                raw = pd.to_numeric(raw, errors="coerce")
                # Deteksi unit: unix detik < 2e10, milidetik >= 1e12
                sample = raw.dropna().iloc[0] if raw.dropna().shape[0] > 0 else 0
                unit = "ms" if sample > 1e11 else "s"
                dt_col = pd.to_datetime(raw, unit=unit, errors="coerce")
                break
        if dt_col is not None:
            df["_dt"] = dt_col
            # Hapus semua kolom datetime lama agar tidak bentrok
            for c in ("unix_timestamp", "unixdate", "datetime", "date", "timestamp", "time", "t"):
                if c in df.columns:
                    df = df.drop(columns=[c], errors="ignore")
            df = df.rename(columns={"_dt": "datetime"})
            df = df.drop_duplicates(subset=["datetime"], keep="last")
            df = df.dropna(subset=["datetime"])
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)

        # Jangan spam INFO untuk 800+ saham; cukup DEBUG.
        logger.debug(f"[{symbol}] OHLCV OK: {len(df)} candle ({interval})")
        return df

    except Exception as e:
        logger.error(f"[{symbol}] Error parsing OHLCV: {e}")
        return None


# ---------------------------------------------------------------
# 2. Stock Info -- harga realtime, sektor
# ---------------------------------------------------------------
def fetch_stock_info(symbol: str) -> Optional[Dict]:
    """GET /api/emiten/{symbol}/info"""
    data = _get(f"/api/emiten/{symbol}/info")
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else None


def parse_keystats_market_cap_billions(raw: Optional[Any]) -> float:
    """
    Parse string market cap dari keystats, mis. '727,323 B' → angka 727323 (Miliar IDR)
    untuk peringkat relatif antar saham.
    """
    if not raw:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().upper().replace(",", "")
    num = ""
    for ch in s:
        if ch.isdigit() or ch == ".":
            num += ch
        elif ch in ("B", "T", "M"):
            break
        elif ch.isspace():
            continue
    try:
        return float(num) if num else 0.0
    except ValueError:
        return 0.0


def fetch_keystats_market_cap_billions(symbol: str) -> float:
    """GET /api/emiten/{symbol}/keystats → stats.market_cap sebagai angka peringkat."""
    data = _get(f"/api/emiten/{symbol}/keystats")
    if not data:
        return 0.0
    inner = data.get("data", data) if isinstance(data, dict) else None
    if not isinstance(inner, dict):
        return 0.0
    stats = inner.get("stats")
    if not isinstance(stats, dict):
        return 0.0
    return parse_keystats_market_cap_billions(stats.get("market_cap"))


# ---------------------------------------------------------------
# 3-5. Broker/Movers
# Fungsi dipertahankan untuk kompatibilitas kode lainnya.
# ---------------------------------------------------------------
# Klasifikasi aliran dari field `type` per baris broker summary (API Market Detector).
# Non-retail eksplisit: Asing + Pemerintah. "Lokal" = broker domestik (campuran ritel & institusi).
_NON_RETAIL_INV_TYPES = frozenset({"asing", "pemerintah"})
_LOKAL_INV_TYPES = frozenset({"lokal"})


def _investor_type_key(row: Optional[Dict]) -> str:
    return str((row or {}).get("type") or "").strip().lower()


def compute_non_retail_flow_metrics(
    brokers_buy: List,
    brokers_sell: List,
) -> Dict[str, float]:
    """
    Hitung proporsi nilai BELI dan net flow untuk investor non-retail (Asing + Pemerintah)
    vs sisi lokal (proxy ritel campuran).
    """
    buy_list = brokers_buy or []
    sell_list = brokers_sell or []

    buy_total = sum(float(b.get("bval", 0) or 0) for b in buy_list)

    buy_nr = 0.0
    buy_lokal = 0.0
    for b in buy_list:
        t = _investor_type_key(b)
        v = float(b.get("bval", 0) or 0)
        if t in _NON_RETAIL_INV_TYPES:
            buy_nr += v
        elif t in _LOKAL_INV_TYPES:
            buy_lokal += v

    net_nr = 0.0
    for b in buy_list:
        if _investor_type_key(b) in _NON_RETAIL_INV_TYPES:
            net_nr += float(b.get("bval", 0) or 0)
    for s in sell_list:
        if _investor_type_key(s) in _NON_RETAIL_INV_TYPES:
            net_nr += float(s.get("sval", 0) or 0)

    non_retail_buy_pct = (100.0 * buy_nr / buy_total) if buy_total > 0 else 0.0
    lokal_buy_pct = (100.0 * buy_lokal / buy_total) if buy_total > 0 else 0.0

    return {
        "non_retail_buy_pct": round(non_retail_buy_pct, 2),
        "lokal_buy_pct": round(lokal_buy_pct, 2),
        "non_retail_net": round(net_nr, 2),
        "buy_total_value": round(buy_total, 2),
        "buy_non_retail_value": round(buy_nr, 2),
        "buy_lokal_value": round(buy_lokal, 2),
    }


def fetch_broker_summary(symbol: str, target_date: str = None) -> Optional[Dict]:
    """
    GET /api/market-detector/broker-summary/{symbol}
    Menarik data broker khusus 1 hari (1D).
    target_date format: YYYY-MM-DD
    """
    if not target_date:
        from datetime import datetime
        import pytz
        WIB = pytz.timezone("Asia/Jakarta")
        target_date = datetime.now(WIB).strftime("%Y-%m-%d")

    params = {
        "from": target_date,
        "to": target_date,
        "transactionType": "TRANSACTION_TYPE_NET",
        "marketBoard": "MARKET_BOARD_ALL",
        "investorType": "INVESTOR_TYPE_ALL"
    }
    
    data = _get(f"/api/market-detector/broker-summary/{symbol}", params=params)
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else None

def fetch_broker_summary_with_fallback(
    symbol: str,
    max_lookback_days: int = 7,
    start_date: Optional[str] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Coba broker summary untuk hari ini (WIB). Jika data belum tersedia,
    mundurkan tanggal sampai ketemu data, maksimal `max_lookback_days`.

    Return: (raw_json, used_date_yyyy_mm_dd)
    """
    from datetime import datetime, timedelta
    import pytz

    WIB = pytz.timezone("Asia/Jakarta")

    if start_date:
        try:
            d = datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            d = datetime.now(WIB).date()
    else:
        d = datetime.now(WIB).date()

    def _has_non_empty_broksum(raw_obj: Any) -> bool:
        """True jika brokers_buy/sell ada isinya (bukan sekadar response kosong)."""
        if not isinstance(raw_obj, dict):
            return False
        # raw bisa: {"message":..., "data":{...}} atau langsung inner dict
        data = raw_obj.get("data", raw_obj)
        if not isinstance(data, dict):
            return False
        bs = data.get("broker_summary", {})
        if not isinstance(bs, dict):
            return False
        buys = bs.get("brokers_buy", []) or []
        sells = bs.get("brokers_sell", []) or []
        return len(buys) > 0 or len(sells) > 0

    # mundur kalender (tidak asumsi hari bursa di API), stop saat ketemu data yang BERISI
    for i in range(max_lookback_days + 1):
        target = (d - timedelta(days=i)).strftime("%Y-%m-%d")
        raw = fetch_broker_summary(symbol, target_date=target)
        if raw and _has_non_empty_broksum(raw):
            return raw, target
    return None, None


def parse_broker_summary(raw: Optional[Dict]) -> Optional[Dict]:
    """
    Parse hasil dari fetch_broker_summary khusus 1 hari.
    Return dictionary seragam seperti parse_broker_chart.
    """
    if not raw:
        return None

    # fetch_broker_summary() sudah melakukan unwrap `data` jika response berbentuk dict.
    # Tapi ada kemungkinan caller mengirim response mentah (masih ada key `data`).
    # Jadi parse harus bisa handle keduanya.
    if isinstance(raw, dict) and "broker_summary" in raw:
        data = raw
    elif isinstance(raw, dict):
        data = raw.get("data", raw) or {}
    else:
        return None

    broker_summary = data.get("broker_summary", {}) if isinstance(data, dict) else {}
    if not broker_summary:
        return None
        
    brokers_buy = broker_summary.get("brokers_buy", [])
    brokers_sell = broker_summary.get("brokers_sell", [])
    
    if not brokers_buy and not brokers_sell:
        return None
    
    top_buyers = []
    total_buy = 0.0
    for b in brokers_buy:
        code = b.get("netbs_broker_code")
        val = float(b.get("bval", 0))
        total_buy += val
        if code and val > 0:
            top_buyers.append({"code": code, "net": val})
            
    top_sellers = []
    total_sell = 0.0
    for s in brokers_sell:
        code = s.get("netbs_broker_code")
        # sval is already negative in the JSON response
        val = float(s.get("sval", 0))
        total_sell += val
        if code and val < 0:
            top_sellers.append({"code": code, "net": val})
            
    total_net = total_buy + total_sell
    
    # Sort descending untuk buyer, ascending untuk seller (paling negatif = paling atas)
    top_buyers = sorted(top_buyers, key=lambda x: x["net"], reverse=True)[:3]
    top_sellers = sorted(top_sellers, key=lambda x: x["net"])[:3]
    
    if total_buy > abs(total_sell):
        dominant = "BUYING"
    elif abs(total_sell) > total_buy:
        dominant = "SELLING"
    else:
        dominant = "NEUTRAL"
        
    # ── Bandar summary (Objective ALL brokers, 1D) ──
    detector = data.get("bandar_detector", {}) if isinstance(data, dict) else {}
    accdist_raw = ""
    accdist_amount = 0.0
    accdist_percent = 0.0
    accdist_source = "ALL"
    bandar_total_value = 0.0
    bandar_total_buyer = 0
    bandar_total_seller = 0

    def _pick_detector(name: str) -> Optional[Dict]:
        v = detector.get(name)
        return v if isinstance(v, dict) else None

    # Prefer broker_accdist, otherwise pick the most meaningful bucket
    if isinstance(detector, dict):
        accdist_raw = str(detector.get("broker_accdist") or "").strip()
        try:
            bandar_total_value = float(detector.get("value", 0) or 0)
        except Exception:
            bandar_total_value = 0.0
        try:
            bandar_total_buyer = int(detector.get("total_buyer", 0) or 0)
        except Exception:
            bandar_total_buyer = 0
        try:
            bandar_total_seller = int(detector.get("total_seller", 0) or 0)
        except Exception:
            bandar_total_seller = 0

        # ── Konsentrasi Buyer ──────────────────────────────────────────────────
        # Konsep: dari total transaksi harian (buy + sell, dua sisi),
        # berapa persen yang merupakan aksi BELI?
        # Contoh: buy=Rp67M, sell=Rp381M → total=Rp448M → konsentrasi beli=14.9%
        #
        # PENTING: bandar_total_value dari API = nilai buy side saja (bukan grand total)
        # sehingga total_buy / bandar_total_value selalu = 100%. Jangan pakai itu.
        # Gunakan total_buy + abs(total_sell) sebagai grand total dua sisi.
        #
        # accdist_amount → total nilai beli semua broker (positif)
        # accdist_percent → % beli dari grand total (buy + sell)
        accdist_amount = total_buy
        grand_total = total_buy + abs(total_sell)
        if grand_total > 0:
            accdist_percent = (accdist_amount / grand_total) * 100.0
        else:
            accdist_percent = 0.0
        if not accdist_raw:
            accdist_raw = "Acc" if total_net > 0 else ("Dist" if total_net < 0 else "Neutral")

    accdist_u = accdist_raw.upper()
    # Label berdasarkan konsentrasi beli (% dari total transaksi harian).
    # Threshold konsentrasi:
    #   ≥ 40% → BIG_ACC  (sangat terkonsentrasi, dominasi kuat)
    #   ≥ 25% → ACC      (konsentrasi cukup signifikan)
    #   ≥ 10% → WATCH    (mulai terlihat konsentrasi)
    #   < 10% → NEUTRAL  (transaksi tersebar, tidak ada dominasi)
    # Note: "DIST" dihilangkan karena metrik ini adalah konsentrasi beli,
    # bukan arah net. Arah net sudah ada di field `dominant`.
    if accdist_percent >= 40.0:
        accdist_label = "BIG_ACC"
    elif accdist_percent >= 25.0:
        accdist_label = "ACC"
    elif accdist_percent >= 10.0:
        accdist_label = "WATCH"
    else:
        accdist_label = "NEUTRAL"

    nr_metrics = compute_non_retail_flow_metrics(brokers_buy, brokers_sell)

    return {
        "brokers": [b["code"] for b in top_buyers] + [s["code"] for s in top_sellers],
        "top_buyers": top_buyers,
        "top_sellers": top_sellers,
        "total_net": total_net,
        "dominant": dominant,
        "n_buy": len(brokers_buy),
        "n_sell": len(brokers_sell),
        "days": 1,
        "has_broker_data": True,
        "bandar_accdist_raw": accdist_raw,
        "bandar_accdist": accdist_label,
        "bandar_source": accdist_source,
        "bandar_amount": accdist_amount,          # total beli (Rp)
        "bandar_percent": accdist_percent,         # % beli dari grand total
        "bandar_grand_total": grand_total,         # buy + abs(sell) — denominator yg benar
        "bandar_total_value": bandar_total_value,  # raw dari API (jangan pakai utk %)
        "bandar_total_buyer": bandar_total_buyer,
        "bandar_total_seller": bandar_total_seller,
        # Non-retail-flow (dari kolom `type` per broker: Asing, Pemerintah, Lokal)
        "non_retail_buy_pct": nr_metrics["non_retail_buy_pct"],
        "lokal_buy_pct": nr_metrics["lokal_buy_pct"],
        "non_retail_net": nr_metrics["non_retail_net"],
    }

def fetch_top_brokers(symbol: str, rank_by: str = "netValue") -> Optional[Any]:
    """GET /api/broker/top/{symbol}"""
    data = _get(f"/api/broker/top/{symbol}", params={"rankBy": rank_by})
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else data

def fetch_movers(mover_type: str = "net_foreign_buy", limit: int = 20) -> Optional[List]:
    """GET /api/main/movers"""
    data = _get("/api/main/movers", params={"type": mover_type, "limit": limit})
    if not data:
        return None
    if isinstance(data, list):
        return data
    return data.get("data", data) if isinstance(data, dict) else data


def fetch_foreign_ownership(symbol: str) -> Optional[Dict]:
    """
    GET /api/emiten/{symbol}/foreign-ownership
    Data kepemilikan asing: institutionOwnership, fundOwnership, summary.
    Response: { symbol, institutionOwnership, fundOwnership, summary, timestamp }
    Return: dict atau None.
    """
    data = _get(f"/api/emiten/{symbol}/foreign-ownership")
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else None


# ---------------------------------------------------------------
# 6. Bundle bandarmology
# ---------------------------------------------------------------
def fetch_bandarmology_bundle(symbol: str) -> Dict[str, Any]:
    """
    Bundle data untuk bandarmology.

    Ultra:
      - Broker summary 1D (top buyer/top seller net) + fallback tanggal

    Note: dibuat sebagai "one stop" supaya scanner tidak request dobel.
    """
    broksum_raw, broksum_date = fetch_broker_summary_with_fallback(symbol, max_lookback_days=7)
    broksum = parse_broker_summary(broksum_raw)

    return {
        "broksum_raw": broksum_raw,
        "broksum_date": broksum_date,
        "broksum": broksum,
    }


# ---------------------------------------------------------------
# 7. Macro endpoints
# ---------------------------------------------------------------
def fetch_morning_briefing() -> Optional[Dict]:
    """GET /api/main/morning-briefing -- outlook pasar pagi."""
    data = _get("/api/main/morning-briefing")
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else data

def fetch_forex_idr_impact() -> Optional[Dict]:
    """GET /api/main/forex-idr-impact -- dampak kurs USD/IDR."""
    data = _get("/api/main/forex-idr-impact")
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else data

def fetch_commodities_impact() -> Optional[Dict]:
    """GET /api/main/commodities-impact -- harga komoditas."""
    data = _get("/api/main/commodities-impact")
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else data

def fetch_trending_stocks() -> Optional[List]:
    """GET /api/main/trending-stocks -- saham trending hari ini."""
    data = _get("/api/main/trending-stocks")
    if not data:
        return None
    if isinstance(data, list):
        return data
    return data.get("data", data) if isinstance(data, dict) else data

def fetch_all_symbols() -> List[str]:
    """GET /api/main/symbols -- Semua saham IHSG yang aktif (kode unik, terurut)."""
    data = _get("/api/main/symbols")
    if not data:
        return []
    raw = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        if isinstance(x, str):
            s = x.strip().upper()
        elif isinstance(x, dict):
            s = str(
                x.get("symbol") or x.get("code") or x.get("ticker") or ""
            ).strip().upper()
        else:
            continue
        if s and len(s) >= 3:
            out.append(s)
    return sorted(set(out))


# ---------------------------------------------------------------
# 8. Broker Trade Chart
# Data: top 5 broker net value per jam, 7 hari terakhir
# ---------------------------------------------------------------

def fetch_broker_chart(symbol: str) -> Optional[Dict]:
    """
    GET /api/emiten/{symbol}/broker-trade-chart
    Return dict mentah (key: broker_chart_data, price_chart_data) atau None.
    """
    from config.settings import BROKER_CHART_ENABLED
    if not BROKER_CHART_ENABLED:
        return None
    data = _get(f"/api/emiten/{symbol}/broker-trade-chart")
    if not data:
        return None
    return data.get("data", data) if isinstance(data, dict) else None


def parse_broker_chart(raw: Optional[Dict]) -> Optional[Dict]:
    """
    Parse getBrokerTradeChart → ringkasan net per broker 7 hari.

    Return:
    {
        "brokers":       ["XL","SQ","CC","AK","BK"],
        "net_by_broker": {"XL": 12_500_000_000, "SQ": -3_200_000_000, ...},
        "top_buyers":    [{"code": "XL", "net": 12_500_000_000}, ...],  # top 3 net beli
        "top_sellers":   [{"code": "SQ", "net": -3_200_000_000}, ...],  # top 3 net jual
        "total_net":     9_300_000_000,
        "dominant":      "BUYING",   # BUYING / SELLING / NEUTRAL
        "n_buy":         3,          # jumlah broker net beli
        "n_sell":        2,          # jumlah broker net jual
        "days":          5,
    }
    """
    if not raw:
        return None

    # raw bisa berupa dict dengan key broker_chart_data, atau langsung list
    if isinstance(raw, dict):
        entries = raw.get("broker_chart_data", [])
    elif isinstance(raw, list):
        entries = raw
    else:
        return None

    # Ambil entry TYPE_CHART_VALUE (net Rupiah) — lebih informatif dari lot
    chart_entry = None
    for e in entries:
        if isinstance(e, dict) and "VALUE" in str(e.get("type", "")):
            chart_entry = e
            break
    if not chart_entry and entries:
        chart_entry = entries[0]
    if not chart_entry:
        return None

    brokers = chart_entry.get("brokers", [])
    charts  = chart_entry.get("charts", [])

    # Hitung net per broker: sum semua candle net value
    net_by_broker: Dict[str, float] = {}
    days_seen: set = set()
    for candle in charts:
        date = candle.get("date") or candle.get("d")
        if date:
            days_seen.add(date)
        nets = candle.get("net", candle.get("n", []))
        for idx, code in enumerate(brokers):
            v = 0.0
            if isinstance(nets, list) and idx < len(nets):
                try:
                    v = float(nets[idx] or 0)
                except (ValueError, TypeError):
                    v = 0.0
            net_by_broker[code] = net_by_broker.get(code, 0.0) + v

    if not net_by_broker:
        return None

    total_net   = sum(net_by_broker.values())
    top_buyers  = sorted(
        [{"code": c, "net": v} for c, v in net_by_broker.items() if v > 0],
        key=lambda x: x["net"], reverse=True
    )[:3]
    top_sellers = sorted(
        [{"code": c, "net": v} for c, v in net_by_broker.items() if v < 0],
        key=lambda x: x["net"]
    )[:3]

    n_buy  = sum(1 for v in net_by_broker.values() if v > 0)
    n_sell = sum(1 for v in net_by_broker.values() if v < 0)

    if total_net > 0:
        dominant = "BUYING"
    elif total_net < 0:
        dominant = "SELLING"
    else:
        dominant = "NEUTRAL"

    return {
        "brokers":        list(net_by_broker.keys()),
        "net_by_broker":  net_by_broker,
        "top_buyers":     top_buyers,
        "top_sellers":    top_sellers,
        "total_net":      total_net,
        "dominant":       dominant,
        "n_buy":          n_buy,
        "n_sell":         n_sell,
        "days":           len(days_seen) or 1,
        "has_broker_data": True,
    }


    n_buy  = sum(1 for v in net_by_broker.values() if v > 0)
    n_sell = sum(1 for v in net_by_broker.values() if v < 0)

    if total_net > 0:
        dominant = "BUYING"
    elif total_net < 0:
        dominant = "SELLING"
    else:
        dominant = "NEUTRAL"

    return {
        "brokers":       list(net_by_broker.keys()),
        "net_by_broker": net_by_broker,
        "top_buyers":    top_buyers,
        "top_sellers":   top_sellers,
        "total_net":     total_net,
        "dominant":      dominant,
        "n_buy":         n_buy,
        "n_sell":        n_sell,
        "days":          len(days_seen),
    }
