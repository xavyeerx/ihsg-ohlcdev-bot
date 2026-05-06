# ============================================================
# ENGINE FRESH FILTER — only send "new" engine items
# ============================================================
import json
import logging
import os
import hashlib
from typing import Any, Dict, List, Set, Optional

logger = logging.getLogger(__name__)

_SEEN_FILE = os.path.join(os.path.dirname(__file__), "..", "database", "engine_seen.json")


def _load_seen() -> Set[str]:
    path = os.path.abspath(_SEEN_FILE)
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(x) for x in data)
        if isinstance(data, dict) and "ids" in data:
            return set(str(x) for x in data["ids"])
    except Exception as e:
        logger.warning(f"engine_seen read: {e}")
    return set()


def _save_seen(seen: Set[str]) -> None:
    path = os.path.abspath(_SEEN_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ids": sorted(seen)[-6000:]}, f, indent=2)
    except Exception as e:
        logger.warning(f"engine_seen write: {e}")


def _stable_hash(obj: Any) -> str:
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        raw = str(obj)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:14]


def _row_id(prefix: str, row: Any) -> str:
    if not isinstance(row, dict):
        return f"{prefix}|raw|{_stable_hash(row)}"
    sym = str(row.get("symbol") or row.get("ticker") or row.get("code") or "").strip().upper()
    dt = str(
        row.get("date")
        or row.get("dateObj")
        or row.get("updated_at")
        or row.get("updatedAt")
        or row.get("timestamp")
        or row.get("time")
        or ""
    ).strip()
    core = {
        "symbol": sym,
        "dt": dt[:40],
        "k": row.get("type") or row.get("actionType") or row.get("status") or row.get("severity") or "",
    }
    return f"{prefix}|{sym}|{dt[:20]}|{_stable_hash(core)}|{_stable_hash(row)}"


def _filter_list(prefix: str, rows: Optional[List], seen: Set[str]) -> List:
    out = []
    for r in rows or []:
        eid = _row_id(prefix, r)
        if eid in seen:
            continue
        seen.add(eid)
        out.append(r)
    return out


def filter_fresh_engine_results(engine_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return engine_results versi "fresh only":
    - sweep/bandar/insider/whale/sector: filter list items yang belum pernah dikirim.
    - events: pakai diff kalender yang sudah ada (calendar_seen.json).
    """
    if not engine_results:
        return {}

    seen = _load_seen()
    changed = False

    out = dict(engine_results)

    sweep = engine_results.get("sweep")
    if sweep:
        sweep2 = sweep
        sweep2.top_gainers = _filter_list("SWEEP_GAIN", getattr(sweep, "top_gainers", None), seen)
        sweep2.breakout_stocks = _filter_list("SWEEP_BRK", getattr(sweep, "breakout_stocks", None), seen)
        sweep2.multibagger = _filter_list("SWEEP_MB", getattr(sweep, "multibagger", None), seen)
        sweep2.trending = _filter_list("SWEEP_TR", getattr(sweep, "trending", None), seen)
        out["sweep"] = sweep2
        changed = True

    bandar = engine_results.get("bandar")
    if bandar:
        bandar2 = bandar
        bandar2.accumulation = _filter_list("BANDAR_ACC", getattr(bandar, "accumulation", None), seen)
        bandar2.distribution = _filter_list("BANDAR_DIST", getattr(bandar, "distribution", None), seen)
        bandar2.smart_money = _filter_list("BANDAR_SM", getattr(bandar, "smart_money", None), seen)
        bandar2.pump_dump = _filter_list("BANDAR_PUMP", getattr(bandar, "pump_dump", None), seen)
        out["bandar"] = bandar2
        changed = True

    insider = engine_results.get("insider")
    if insider:
        insider2 = insider
        insider2.all_insider = _filter_list("INSIDER", getattr(insider, "all_insider", None), seen)
        out["insider"] = insider2
        changed = True

    sector = engine_results.get("sector")
    if sector:
        sector2 = sector
        sector2.hot_sectors = _filter_list("SECTOR_HOT", getattr(sector, "hot_sectors", None), seen)
        sector2.hot_stocks = _filter_list("SECTOR_STK", getattr(sector, "hot_stocks", None), seen)
        out["sector"] = sector2
        changed = True

    whale = engine_results.get("whale")
    if whale:
        whale2 = whale
        whale2.whale_txns = _filter_list("WHALE", getattr(whale, "whale_txns", None), seen)
        out["whale"] = whale2
        changed = True

    events = engine_results.get("events")
    if events:
        try:
            # Reuse cache calendar yang sudah ada
            from notifications.calendar_alerts import diff_new_calendar_items

            items = diff_new_calendar_items(events)
            if items:
                ev2 = events
                # reset dulu semua list
                ev2.dividends = []
                ev2.rights_issue = []
                ev2.stock_split = []
                ev2.rups = []
                for it in items:
                    kind = it.get("kind")
                    row = it.get("row")
                    if kind == "dividen":
                        ev2.dividends.append(row)
                    elif kind == "rights_issue":
                        ev2.rights_issue.append(row)
                    elif kind == "stock_split":
                        ev2.stock_split.append(row)
                    elif kind == "rups":
                        ev2.rups.append(row)
                out["events"] = ev2
                changed = True
            else:
                # no fresh events -> empty lists so telegram won't repeat
                ev2 = events
                ev2.dividends = []
                ev2.rights_issue = []
                ev2.stock_split = []
                ev2.rups = []
                out["events"] = ev2
        except Exception as e:
            logger.warning(f"fresh events diff: {e}")

    if changed:
        _save_seen(seen)
    return out

