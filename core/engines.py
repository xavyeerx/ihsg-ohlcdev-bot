# ============================================================
# ENGINES — Multi-signal engine untuk IDX Intelligence Bot
# ============================================================
#
# Engine list (plan ULTRA aktif):
#   Engine 1 — Teknikal          ✅ (scanner.py)
#   Engine 2 — Market Sweep      ✅ (getMarketMover, getBreakoutAlerts, dll)
#   Engine 3 — Bandarmology API  ✅ (getBandarAccumulation, getSmartMoneyFlow, dll)
#   Engine 4 — Insider           ✅ (getAllInsiderTrading, getInsiderNetSummary)
#   Engine 5 — Sectoral          ✅ (getSectorRotation, getIndicesImpact)
#   Engine 6 — Corporate Events  ✅ (getDividendCalendar, getBreakoutAlerts, dll)
#   Engine 7 — Whale & Smart $   ✅ (getWhaleTransactions, getSmartMoneyFlow)
# ============================================================

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.data_fetcher import _get

logger = logging.getLogger(__name__)


# ── Dataclass hasil per engine ────────────────────────────────

@dataclass
class MarketSweepResult:
    """Hasil Engine 2 — Market-level sweep."""
    available:      bool  = False   # False = butuh Ultra
    top_gainers:    List  = field(default_factory=list)
    top_losers:     List  = field(default_factory=list)
    top_value:      List  = field(default_factory=list)
    net_foreign_buy:List  = field(default_factory=list)
    breakout_stocks:List  = field(default_factory=list)  # getBreakoutAlerts
    multibagger:    List  = field(default_factory=list)  # scanMultibagger
    trending:       List  = field(default_factory=list)  # getTrendingStocks
    shortlist:      List  = field(default_factory=list)  # gabungan semua, dedup


@dataclass
class BandarAPIResult:
    """Hasil Engine 3 — Bandarmology API (bukan kalkulasi manual)."""
    available:      bool  = False
    accumulation:   List  = field(default_factory=list)  # getBandarAccumulation
    distribution:   List  = field(default_factory=list)  # getBandarDistribution
    smart_money:    List  = field(default_factory=list)  # getSmartMoneyFlow
    pump_dump:      List  = field(default_factory=list)  # getPumpDumpDetection — AVOID list
    retail_bandar:  Dict  = field(default_factory=dict)  # getRetailBandarSentiment


@dataclass
class InsiderResult:
    """Hasil Engine 4 — Insider trading."""
    available:      bool  = False
    all_insider:    List  = field(default_factory=list)  # getAllInsiderTrading
    net_summary:    Dict  = field(default_factory=dict)  # getInsiderNetSummary
    # Per-saham diambil saat deep scan: getInsiderTradingBySymbol


@dataclass
class SectorResult:
    """Hasil Engine 5 — Sektor rotation."""
    available:      bool  = False
    rotation:       Dict  = field(default_factory=dict)  # getSectorRotation
    indices_impact: Dict  = field(default_factory=dict)  # getIndicesImpact
    global_overview:Dict  = field(default_factory=dict)  # getGlobalMarketOverview
    hot_sectors:    List  = field(default_factory=list)  # sektor dengan inflow terbesar
    hot_stocks:     List  = field(default_factory=list)  # saham dari sektor hot


@dataclass
class EventResult:
    """Hasil Engine 6 — Corporate events / calendar."""
    available:      bool  = False
    dividends:      List  = field(default_factory=list)  # getDividendCalendar
    ipo:            List  = field(default_factory=list)  # getIpoCalendar + getIpoMomentum
    rights_issue:   List  = field(default_factory=list)  # getRightIssueCalendar
    stock_split:    List  = field(default_factory=list)  # getStockSplitCalendar
    rups:           List  = field(default_factory=list)  # getRupsCalendar
    today_actions:  List  = field(default_factory=list)  # getTodayCorporateActions
    economic_cal:   List  = field(default_factory=list)  # getEconomicCalendar


@dataclass
class WhaleResult:
    """Hasil Engine 7 — Whale & Smart Money."""
    available:      bool  = False
    whale_txns:     List  = field(default_factory=list)  # getWhaleTransactions
    broker_summary: List  = field(default_factory=list)  # getBrokerSummary (market-level)
    top_brokers:    List  = field(default_factory=list)  # getTopBrokers
    broker_activity:List  = field(default_factory=list)  # getBrokerActivity


# ── Engine 2: Market Sweep ────────────────────────────────────

def run_market_sweep() -> MarketSweepResult:
    """
    Engine 2 — Market-level sweep (1 run = dapat shortlist saham menarik).
    Hemat quota: semua endpoint return data seluruh pasar, bukan per-saham.

    🔒 ULTRA required:
        getMarketMover, getBreakoutAlerts, scanMultibagger,
        getTrendingStocks, getSectorCompanies
    """
    result = MarketSweepResult()

    def _extract_list(raw: Any, preferred_keys: Optional[List[str]] = None) -> List:
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        if not isinstance(raw, dict):
            return []
        d0 = raw.get("data", raw)
        if isinstance(d0, list):
            return d0
        if not isinstance(d0, dict):
            return []
        if preferred_keys:
            for k in preferred_keys:
                v = d0.get(k)
                if isinstance(v, list):
                    return v
        d1 = d0.get("data")
        if isinstance(d1, list):
            return d1
        if isinstance(d1, dict):
            if preferred_keys:
                for k in preferred_keys:
                    v = d1.get(k)
                    if isinstance(v, list):
                        return v
        return []

    # ── getMarketMover ──────────────────────────────────────
    # Endpoint movers lama sering 400 karena kontrak parameter berubah.
    # Skip sementara agar log bersih; shortlist tetap kuat dari breakout+multibagger+trending.

    # ── getBreakoutAlerts ───────────────────────────────────
    raw = _get("/api/analysis/retail/breakout/alerts")
    if raw:
        result.breakout_stocks = _extract_list(raw, preferred_keys=["alerts", "breakout_alerts"])
        result.available = True

    # ── scanMultibagger ─────────────────────────────────────
    raw = _get("/api/analysis/retail/multibagger/scan")
    if raw:
        result.multibagger = _extract_list(raw, preferred_keys=["candidates", "multibagger"])
        result.available = True

    # ── getTrendingStocks ───────────────────────────────────
    raw = _get("/api/main/trending")
    if raw:
        result.trending = _extract_list(raw, preferred_keys=["data", "trending", "stocks"])
        result.available = True

    # ── Build shortlist (dedup by symbol) ──────────────────
    if result.available:
        seen = set()
        for lst in [result.breakout_stocks, result.multibagger,
                    result.trending, result.top_value]:
            for item in lst:
                sym = item.get("symbol") or item.get("ticker") or item.get("code", "")
                if sym and sym not in seen:
                    seen.add(sym)
                    result.shortlist.append(sym)
        logger.info(f"[MarketSweep] Shortlist: {len(result.shortlist)} saham")

    return result


# ── Engine 3: Bandarmology API ────────────────────────────────

def run_bandar_api() -> BandarAPIResult:
    """
    Engine 3 — Bandarmology API (data siap pakai dari API, bukan kalkulasi manual).

    🔒 ULTRA required:
        getBandarAccumulation, getBandarDistribution,
        getSmartMoneyFlow, getPumpDumpDetection,
        getRetailBandarSentiment
    """
    result = BandarAPIResult()

    # Endpoint bandar terbaru bersifat per-symbol:
    #   /api/analysis/bandar/{accumulation|distribution|smart-money|pump-dump}/{symbol}
    # Ambil universe kecil dari trending agar tetap hemat API call.
    syms: List[str] = []
    raw_trending = _get("/api/main/trending")
    if raw_trending and isinstance(raw_trending, dict):
        d0 = raw_trending.get("data", {})
        d1 = d0.get("data", d0) if isinstance(d0, dict) else d0
        if isinstance(d1, list):
            for row in d1:
                if not isinstance(row, dict):
                    continue
                s = str(row.get("symbol") or row.get("ticker") or row.get("code") or "").strip().upper()
                if s:
                    syms.append(s)
    syms = list(dict.fromkeys(syms))[:12]

    for s in syms:
        ra = _get(f"/api/analysis/bandar/accumulation/{s}")
        if isinstance(ra, dict) and isinstance(ra.get("data"), dict):
            row = dict(ra["data"])
            row["symbol"] = row.get("symbol") or s
            status = str(row.get("status") or "").upper()
            score = float(row.get("accumulation_score", 0) or 0)
            conf = float(row.get("confidence", 0) or 0)
            # Masukkan hanya sinyal akumulasi yang benar-benar aktif.
            if "ACCUMULATION" in status and status != "NEUTRAL" and (score >= 6.0 or conf >= 70):
                result.accumulation.append(row)
                result.available = True

        rd = _get(f"/api/analysis/bandar/distribution/{s}")
        if isinstance(rd, dict) and isinstance(rd.get("data"), dict):
            row = dict(rd["data"])
            row["symbol"] = row.get("symbol") or s
            status = str(row.get("status") or "").upper()
            score = float(row.get("distribution_score", 0) or 0)
            conf = float(row.get("confidence", 0) or 0)
            if "DISTRIBUTION" in status and status != "NEUTRAL" and (score >= 6.0 or conf >= 70):
                result.distribution.append(row)
                result.available = True

        rs = _get(f"/api/analysis/bandar/smart-money/{s}")
        if isinstance(rs, dict) and isinstance(rs.get("data"), dict):
            row = dict(rs["data"])
            row["symbol"] = row.get("symbol") or s
            flow = str(row.get("flow_direction") or "").upper()
            score = float(row.get("smart_money_score", 0) or 0)
            conf = float(row.get("confidence", 0) or 0)
            # Fokus pada inflow smart money (bukan outflow/neutral).
            if "INFLOW" in flow and "OUTFLOW" not in flow and (score >= 4.0 or conf >= 70):
                result.smart_money.append(row)
                result.available = True

        rp = _get(f"/api/analysis/bandar/pump-dump/{s}")
        if isinstance(rp, dict) and isinstance(rp.get("data"), dict):
            row = dict(rp["data"])
            row["symbol"] = row.get("symbol") or s
            status = str(row.get("status") or "").upper()
            risk = float(row.get("risk_score", 0) or 0)
            warns = row.get("warnings", [])
            warn_count = len(warns) if isinstance(warns, list) else 0
            is_risk = status in {"MODERATE_RISK", "HIGH_RISK", "EXTREME_RISK"} or risk >= 5.0 or warn_count >= 2
            if is_risk:
                result.pump_dump.append(row)
                result.available = True

    # Endpoint retail-bandar lama saat ini 404; skip agar log bersih.

    if result.available:
        logger.info(f"[BandarAPI] acc={len(result.accumulation)} "
                    f"dist={len(result.distribution)} "
                    f"smart={len(result.smart_money)} "
                    f"pumpdump={len(result.pump_dump)}")
    return result


# ── Engine 4: Insider ─────────────────────────────────────────

def run_insider_engine() -> InsiderResult:
    """
    Engine 4 — Insider trading seluruh pasar.

    🔒 ULTRA required:
        getAllInsiderTrading (market-level),
        getInsiderNetSummary,
        getInsiderTradingBySymbol (per-saham, dipanggil saat deep scan)
    """
    result = InsiderResult()

    # Endpoint aktif terbaru:
    #   GET /api/analysis/insider-screening
    # Response:
    #   data.summary, data.movements, data.topSymbols, data.topInsiders, data.alerts
    raw = _get("/api/analysis/insider-screening")
    if raw and isinstance(raw, dict):
        data = raw.get("data", raw)
        if isinstance(data, dict):
            movements = data.get("movements")
            if isinstance(movements, list):
                result.all_insider = movements
            summary = data.get("summary")
            if isinstance(summary, dict):
                result.net_summary = summary
            result.available = bool(result.all_insider or result.net_summary)
        elif isinstance(data, list):
            # fallback jika provider sewaktu-waktu mengembalikan list langsung
            result.all_insider = data
            result.available = True

    if result.available:
        logger.info(f"[Insider] {len(result.all_insider)} transaksi insider (screening)")
    return result


def fetch_insider_by_symbol(symbol: str) -> Optional[List]:
    """
    Fetch insider trading untuk satu saham (deep scan).
    🔒 ULTRA required: getInsiderTradingBySymbol
    """
    # Endpoint aktif saat ini: /api/emiten/{symbol}/insider
    raw = _get(f"/api/emiten/{symbol}/insider")
    if raw and isinstance(raw, dict):
        data = raw.get("data", raw)
        if isinstance(data, dict):
            movement = data.get("movement")
            if isinstance(movement, list):
                return movement
        if isinstance(data, list):
            return data
    return None


# ── Engine 5: Sectoral ───────────────────────────────────────

def run_sector_engine() -> SectorResult:
    """
    Engine 5 — Rotasi sektor dan dampak global.

    🔒 ULTRA required:
        getSectorRotation, getIndicesImpact,
        getGlobalMarketOverview, getSectorCompanies
    """
    result = SectorResult()
    # Endpoint sektor/global-market yang dipakai sebelumnya saat ini 404 pada API provider.
    # Nonaktifkan dulu agar tidak spam warning setiap scan.
    return result


# ── Engine 6: Corporate Events ───────────────────────────────

def _extract_calendar_rows(raw: Any, keys: List[str]) -> List[Dict[str, Any]]:
    """
    Normalisasi response calendar API yang sering berbentuk:
      {"success": true, "data": {"data": {"dividend": [...]}}}
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if not isinstance(raw, dict):
        return []

    lvl1 = raw.get("data", raw)
    if isinstance(lvl1, list):
        return [x for x in lvl1 if isinstance(x, dict)]
    if not isinstance(lvl1, dict):
        return []

    lvl2 = lvl1.get("data", lvl1)
    if isinstance(lvl2, list):
        return [x for x in lvl2 if isinstance(x, dict)]
    if not isinstance(lvl2, dict):
        return []

    for k in keys:
        rows = lvl2.get(k)
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _normalize_event_row(kind: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Samakan field minimum agar downstream alert lebih konsisten."""
    norm = dict(row)
    symbol = (
        row.get("symbol")
        or row.get("company_symbol")
        or row.get("ticker")
        or row.get("code")
        or ""
    )
    norm["symbol"] = symbol

    if kind == "dividend":
        norm["ex_date"] = row.get("ex_date") or row.get("dividend_exdate") or row.get("date") or ""
        norm["amount"] = (
            row.get("amount")
            or row.get("dividend_amount")
            or row.get("dividend_value_formatted")
            or row.get("dividend_value")
            or row.get("dividend")
            or ""
        )
    elif kind == "right_issue":
        norm["ex_date"] = row.get("ex_date") or row.get("rightissue_exdate") or row.get("date") or ""
        norm["amount"] = row.get("ratio") or row.get("rightissue_ratio") or row.get("amount") or ""
    elif kind == "stock_split":
        norm["ex_date"] = row.get("ex_date") or row.get("stocksplit_date") or row.get("date") or ""
        norm["amount"] = row.get("ratio") or row.get("stocksplit_ratio") or row.get("amount") or ""
    elif kind == "rups":
        norm["meeting_date"] = row.get("meeting_date") or row.get("rups_date") or row.get("date") or ""
    elif kind == "ipo":
        norm["date"] = row.get("date") or row.get("ipo_listing_date") or row.get("ipo_offering_date") or ""
    elif kind == "economic":
        norm["date"] = row.get("date") or row.get("econcal_date") or ""

    return norm

def run_event_engine() -> EventResult:
    """
    Engine 6 — Corporate events dan calendar.
    Alert H-7, H-3, H-1 sebelum ex-date dividen / rights issue.

    🔒 ULTRA required:
        getDividendCalendar, getIpoCalendar, getRightIssueCalendar,
        getStockSplitCalendar, getRupsCalendar,
        getTodayCorporateActions, getEconomicCalendar, getIpoMomentum
    """
    result = EventResult()

    # ── getDividendCalendar ─────────────────────────────────
    raw = _get("/api/calendar/dividend")
    if raw:
        rows = _extract_calendar_rows(raw, ["dividend", "dividends"])
        result.dividends = [_normalize_event_row("dividend", x) for x in rows]
        result.available = True

    # ── getIpoCalendar + getIpoMomentum ─────────────────────
    raw = _get("/api/calendar/ipo")
    if raw:
        rows = _extract_calendar_rows(raw, ["ipo", "ipos"])
        result.ipo = [_normalize_event_row("ipo", x) for x in rows]
        result.available = True

    # ── getRightIssueCalendar ───────────────────────────────
    raw = _get("/api/calendar/right-issue")
    if raw:
        rows = _extract_calendar_rows(raw, ["rightissue", "right_issue", "rights_issue"])
        result.rights_issue = [_normalize_event_row("right_issue", x) for x in rows]
        result.available = True

    # ── getStockSplitCalendar ───────────────────────────────
    raw = _get("/api/calendar/stock-split")
    if raw:
        rows = _extract_calendar_rows(raw, ["stocksplit", "stock_split"])
        result.stock_split = [_normalize_event_row("stock_split", x) for x in rows]
        result.available = True

    # ── getRupsCalendar ─────────────────────────────────────
    raw = _get("/api/calendar/rups")
    if raw:
        rows = _extract_calendar_rows(raw, ["rups"])
        result.rups = [_normalize_event_row("rups", x) for x in rows]
        result.available = True

    # ── getEconomicCalendar ─────────────────────────────────
    raw = _get("/api/calendar/economic")
    if raw:
        rows = _extract_calendar_rows(raw, ["economic", "events"])
        result.economic_cal = [_normalize_event_row("economic", x) for x in rows]
        result.available = True

    # Endpoint corporate-actions sudah tidak tersedia (404).
    # Ganti fallback: gabungkan event yang tanggalnya hari ini.
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_rows: List[Dict[str, Any]] = []
    for item in (result.dividends + result.rights_issue + result.stock_split + result.rups + result.ipo):
        dt = (
            item.get("ex_date")
            or item.get("meeting_date")
            or item.get("date")
            or ""
        )
        if isinstance(dt, str) and dt[:10] == today_str:
            today_rows.append(item)
    result.today_actions = today_rows

    if result.available:
        logger.info(f"[Events] div={len(result.dividends)} ipo={len(result.ipo)} "
                    f"rights={len(result.rights_issue)} today={len(result.today_actions)}")
    return result


def get_dividend_alerts(event_result: EventResult, days_ahead: int = 7) -> List[Dict]:
    """
    Filter dividen yang ex-date dalam N hari ke depan → alert H-7/H-3/H-1.
    Dipanggil dari scheduler setelah run_event_engine().
    """
    if not event_result.available or not event_result.dividends:
        return []

    from datetime import datetime, timedelta
    import pytz
    WIB     = pytz.timezone("Asia/Jakarta")
    today   = datetime.now(WIB).date()
    cutoff  = today + timedelta(days=days_ahead)
    alerts  = []

    for div in event_result.dividends:
        ex_date_str = div.get("ex_date") or div.get("exDate") or div.get("date", "")
        try:
            ex_date = datetime.strptime(ex_date_str[:10], "%Y-%m-%d").date()
        except:
            continue
        days_left = (ex_date - today).days
        if 0 <= days_left <= days_ahead:
            div["days_to_exdate"] = days_left
            div["urgency"] = "🔴 H-1" if days_left <= 1 else (
                             "🟡 H-3" if days_left <= 3 else "🔵 H-7")
            alerts.append(div)

    return sorted(alerts, key=lambda x: x["days_to_exdate"])


# ── Engine 7: Whale & Smart Money ────────────────────────────

def run_whale_engine() -> WhaleResult:
    """
    Engine 7 — Whale transactions & broker market-level activity.

    🔒 ULTRA required:
        getWhaleTransactions, getBrokerSummary,
        getTopBrokers, getBrokerActivity
    """
    result = WhaleResult()
    # Endpoint whale/market-detector saat ini tidak tersedia (404).
    # Nonaktifkan sementara agar tidak spam warning.
    return result


# ── Per-saham deep scan (Ultra) ───────────────────────────────

def fetch_keystats(symbol: str) -> Optional[Dict]:
    """getKeystats — PBV, PER, EPS, market cap. 🔒 ULTRA"""
    raw = _get(f"/api/emiten/{symbol}/keystats")
    return raw.get("data", raw) if isinstance(raw, dict) else None

def fetch_foreign_ownership(symbol: str) -> Optional[Dict]:
    """getForeignOwnership — tren kepemilikan asing. 🔒 ULTRA"""
    raw = _get(f"/api/emiten/{symbol}/foreign-ownership")
    return raw.get("data", raw) if isinstance(raw, dict) else None

def fetch_holding_composition(symbol: str) -> Optional[Dict]:
    """getHoldingComposition — komposisi pemegang saham. 🔒 ULTRA"""
    raw = _get(f"/api/emiten/{symbol}/holding-composition")
    return raw.get("data", raw) if isinstance(raw, dict) else None

def fetch_technical_analysis(symbol: str) -> Optional[Dict]:
    """getTechnicalAnalysis — TA summary dari API. 🔒 ULTRA"""
    raw = _get(f"/api/advanced/technical-analysis", params={"symbol": symbol})
    return raw.get("data", raw) if isinstance(raw, dict) else None

def fetch_risk_reward(symbol: str) -> Optional[Dict]:
    """calculateRiskReward — R/R otomatis dari API. 🔒 ULTRA"""
    raw = _get(f"/api/analysis/retail/risk-reward/{symbol}")
    return raw.get("data", raw) if isinstance(raw, dict) else None

def fetch_seasonality(symbol: str) -> Optional[Dict]:
    """getSeasonality — pola musiman historis. 🔒 ULTRA"""
    raw = _get(f"/api/emiten/{symbol}/seasonality")
    return raw.get("data", raw) if isinstance(raw, dict) else None


# ── Convenience: jalankan semua engine sekaligus ─────────────

def run_all_engines() -> Dict[str, Any]:
    """
    Jalankan semua engine market-level sekaligus.
    Jalankan semua engine. Engine yang tidak mengembalikan data akan return result dengan available=False.
    Dipanggil dari scheduler saat morning sweep.
    """
    logger.info("[Engines] Running all market-level engines...")

    sweep   = run_market_sweep()
    bandar  = run_bandar_api()
    insider = run_insider_engine()
    sector  = run_sector_engine()
    events  = run_event_engine()
    whale   = run_whale_engine()

    active = sum([
        sweep.available, bandar.available, insider.available,
        sector.available, events.available, whale.available,
    ])
    logger.info(f"[Engines] {active}/6 engine aktif "
                f"({'Tidak ada engine yang aktif — cek koneksi API' if active == 0 else 'OK'})")

    return {
        "sweep":   sweep,
        "bandar":  bandar,
        "insider": insider,
        "sector":  sector,
        "events":  events,
        "whale":   whale,
    }
