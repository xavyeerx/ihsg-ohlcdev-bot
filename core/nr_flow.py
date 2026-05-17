# Non-retail flow — agregasi multi-hari (hemat API: snapshot harian dari scan)
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz

from config.settings import (
    NON_RETAIL_FLOW_5D_TRADING_DAYS,
    NON_RETAIL_FLOW_5D_MIN_PCT,
    NON_RETAIL_FLOW_5D_API_BACKFILL,
    NON_RETAIL_FLOW_5D_MAX_CALENDAR_LOOKBACK,
    TIMEZONE,
)

logger = logging.getLogger(__name__)
WIB = pytz.timezone(TIMEZONE)


def _today_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d")


def record_nr_broksum_snapshot(state: Dict, symbol: str, bandro) -> None:
    """
    Simpan 1 hari broksum ke state (dipanggil tiap scan sukses).
    Tidak ada request API tambahan — data dari fetch_bandarmology_bundle yang sudah jalan.
    """
    if not state or not bandro or not getattr(bandro, "has_broksum", False):
        return
    sym = str(symbol or "").strip().upper()
    if not sym:
        return

    grand = float(getattr(bandro, "broksum_bandar_grand_total", 0) or 0)
    if grand <= 0:
        return

    entry = {
        "date": str(getattr(bandro, "broksum_date", "") or _today_wib())[:10],
        "nr_net": float(getattr(bandro, "broksum_non_retail_net", 0) or 0),
        "grand_total": grand,
        "nr_buy_pct": float(getattr(bandro, "broksum_non_retail_buy_pct", 0) or 0),
        "lokal_buy_pct": float(getattr(bandro, "broksum_lokal_buy_pct", 0) or 0),
        "n_buy": int(getattr(bandro, "broksum_total_buyer", 0) or 0),
        "n_sell": int(getattr(bandro, "broksum_total_seller", 0) or 0),
    }

    bucket = state.setdefault(sym, {})
    if not isinstance(bucket, dict):
        bucket = {}
        state[sym] = bucket

    hist: List[Dict] = list(bucket.get("nr_history") or [])
    hist = [h for h in hist if isinstance(h, dict) and h.get("date") != entry["date"]]
    hist.append(entry)
    hist.sort(key=lambda x: str(x.get("date", "")))
    bucket["nr_history"] = hist[-NON_RETAIL_FLOW_5D_TRADING_DAYS:]


def get_nr_history_from_state(state: Dict, symbol: str) -> List[Dict[str, Any]]:
    """Ambil riwayat NR tersimpan (terurut tanggal naik)."""
    sym = str(symbol or "").strip().upper()
    raw = (state or {}).get(sym, {})
    if not isinstance(raw, dict):
        return []
    hist = raw.get("nr_history") or []
    out = [h for h in hist if isinstance(h, dict) and h.get("date")]
    out.sort(key=lambda x: str(x["date"]))
    return out


def fetch_nr_flow_trading_days(
    symbol: str,
    n_days: int = None,
    max_calendar_lookback: int = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Opsional: ambil broksum dari API (mahal). Hanya jika NON_RETAIL_FLOW_5D_API_BACKFILL=True.
  """
    from datetime import timedelta
    from core.data_fetcher import fetch_broker_summary, parse_broker_summary

    n_days = int(n_days or NON_RETAIL_FLOW_5D_TRADING_DAYS)
    lookback = int(
        max_calendar_lookback if max_calendar_lookback is not None
        else NON_RETAIL_FLOW_5D_MAX_CALENDAR_LOOKBACK
    )
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None

    d = datetime.now(WIB).date()
    collected: List[Dict[str, Any]] = []
    seen = set()

    for offset in range(lookback + 1):
        if len(collected) >= n_days:
            break
        target = (d - timedelta(days=offset)).strftime("%Y-%m-%d")
        if target in seen:
            continue
        raw = fetch_broker_summary(sym, target_date=target)
        if not raw:
            continue
        parsed = parse_broker_summary(raw)
        if not parsed:
            continue
        grand = float(parsed.get("bandar_grand_total", 0) or 0)
        if grand <= 0:
            continue
        seen.add(target)
        collected.append({
            "date": target,
            "nr_net": float(parsed.get("non_retail_net", 0) or 0),
            "grand_total": grand,
            "nr_buy_pct": float(parsed.get("non_retail_buy_pct", 0) or 0),
            "lokal_buy_pct": float(parsed.get("lokal_buy_pct", 0) or 0),
            "n_buy": int(parsed.get("bandar_total_buyer", parsed.get("n_buy", 0)) or 0),
            "n_sell": int(parsed.get("bandar_total_seller", parsed.get("n_sell", 0)) or 0),
        })

    if len(collected) < n_days:
        return None
    collected.sort(key=lambda x: x["date"])
    return collected[-n_days:]


def aggregate_nr_flow_days(days: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agregat net non-retail & grand total dari beberapa hari trading."""
    sum_nr = sum(float(d.get("nr_net", 0) or 0) for d in days)
    sum_grand = sum(float(d.get("grand_total", 0) or 0) for d in days)
    pct = (sum_nr / sum_grand * 100.0) if sum_grand > 0 else 0.0
    latest = days[-1] if days else {}
    return {
        "days": len(days),
        "date_from": days[0]["date"] if days else "",
        "date_to": latest.get("date", ""),
        "sum_nr_net": sum_nr,
        "sum_grand_total": sum_grand,
        "nr_net_pct": pct,
        "latest_nr_buy_pct": float(latest.get("nr_buy_pct", 0) or 0),
        "latest_lokal_buy_pct": float(latest.get("lokal_buy_pct", 0) or 0),
        "latest_n_buy": int(latest.get("n_buy", 0) or 0),
        "latest_n_sell": int(latest.get("n_sell", 0) or 0),
        "daily": days,
    }


def qualifies_nr_flow_5d(agg: Dict[str, Any]) -> bool:
    """Syarat akumulasi 5 hari: net NR positif, % agregat >= threshold, buyer < seller (hari terbaru)."""
    if not agg or agg.get("days", 0) < NON_RETAIL_FLOW_5D_TRADING_DAYS:
        return False
    if float(agg.get("sum_nr_net", 0) or 0) <= 0:
        return False
    if float(agg.get("nr_net_pct", 0) or 0) < NON_RETAIL_FLOW_5D_MIN_PCT:
        return False
    if int(agg.get("latest_n_buy", 0) or 0) >= int(agg.get("latest_n_sell", 0) or 0):
        return False
    return True


def _resolve_nr_5d_days(state: Dict, symbol: str) -> Optional[List[Dict[str, Any]]]:
    """Riwayat dari state; opsional backfill API jika kurang hari."""
    days = get_nr_history_from_state(state, symbol)
    if len(days) >= NON_RETAIL_FLOW_5D_TRADING_DAYS:
        return days[-NON_RETAIL_FLOW_5D_TRADING_DAYS:]

    if not NON_RETAIL_FLOW_5D_API_BACKFILL:
        return None

    logger.info("[%s] NR 5D backfill API (history %d/%d hari)", symbol, len(days), NON_RETAIL_FLOW_5D_TRADING_DAYS)
    return fetch_nr_flow_trading_days(symbol)


def build_nr_flow_5d_candidates(results: list, state: Dict) -> list:
    """
    Saham lolos filter NR 5 hari dari snapshot harian di scan_state.json.
    Tanpa backfill: 0 request API tambahan (hemat quota).
    """
    out = []
    total = len(results or [])
    logger.info(
        "NR flow 5D: cek %d simbol dari history scan (tanpa API tambahan kecuali backfill on)",
        total,
    )
    for r in results or []:
        sym = getattr(r, "symbol", "")
        try:
            days = _resolve_nr_5d_days(state, sym)
            if not days:
                continue
            agg = aggregate_nr_flow_days(days)
            if not qualifies_nr_flow_5d(agg):
                continue
            r.nr_flow_5d_days = agg["days"]
            r.nr_flow_5d_date_from = agg["date_from"]
            r.nr_flow_5d_date_to = agg["date_to"]
            r.nr_flow_5d_net_sum = agg["sum_nr_net"]
            r.nr_flow_5d_grand_sum = agg["sum_grand_total"]
            r.nr_flow_5d_net_pct = agg["nr_net_pct"]
            out.append(r)
        except Exception as e:
            logger.warning("[%s] NR flow 5D error: %s", sym, e)

    out.sort(key=lambda x: float(getattr(x, "nr_flow_5d_net_pct", 0) or 0), reverse=True)
    logger.info("NR flow 5D: selesai — %d/%d simbol lolos (dari history)", len(out), total)
    return out
