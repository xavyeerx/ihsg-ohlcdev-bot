# ============================================================
# MARKET CAP RANKING — untuk filter SM WATCH (top-N kap besar)
# Pakai keystats API + cache file (kurangi panggilan ulang).
# ============================================================
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Set

from core.data_fetcher import fetch_keystats_market_cap_billions

logger = logging.getLogger(__name__)

_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "database", "mcap_cache.json"
)
_CACHE_TTL_SEC = 24 * 3600


def _load_cache() -> Dict[str, Any]:
    path = os.path.abspath(_CACHE_PATH)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {}
        return raw
    except Exception as e:
        logger.warning(f"mcap_cache read error: {e}")
        return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    path = os.path.abspath(_CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"mcap_cache write error: {e}")


def _parse_cached_entry(entry) -> tuple[float, float]:
    """Return (mcap_billions, fetched_ts) atau (0, 0) jika invalid."""
    if isinstance(entry, dict):
        v = float(entry.get("value", 0) or 0)
        ts = float(entry.get("ts", 0) or 0)
        return v, ts
    if isinstance(entry, (int, float)):
        return float(entry), 0.0
    return 0.0, 0.0


def get_top_n_symbols_by_market_cap(
    symbols: List[str],
    n: int = 20,
    ttl_sec: float = _CACHE_TTL_SEC,
) -> Set[str]:
    """
    Ambil set symbol top-N menurut market cap (dari keystats, angka dalam Miliar IDR).

    Cache per-symbol dengan TTL agar tidak membanjiri API setiap scan.
    """
    uniq = sorted(set(s for s in symbols if s))
    if not uniq or n <= 0:
        return set()

    cache = _load_cache()
    now = time.time()
    dirty = False

    for sym in uniq:
        entry = cache.get(sym)
        val, ts = _parse_cached_entry(entry)
        stale = (now - ts) > ttl_sec if ts > 0 else True
        if val > 0 and not stale:
            continue
        mcap = fetch_keystats_market_cap_billions(sym)
        if mcap > 0:
            cache[sym] = {"value": mcap, "ts": now}
            dirty = True
        elif isinstance(entry, dict) and entry.get("value"):
            # pertahankan cache lama jika fetch gagal
            pass
        else:
            cache[sym] = {"value": 0.0, "ts": now}
            dirty = True

    if dirty:
        _save_cache(cache)

    scored: List[tuple[float, str]] = []
    for sym in uniq:
        entry = cache.get(sym)
        val, _ = _parse_cached_entry(entry)
        scored.append((val, sym))

    scored.sort(key=lambda x: (-x[0], x[1]))
    top = [sym for _, sym in scored[:n]]
    logger.info(
        f"[mcap_rank] top-{n} dari {len(uniq)} simbol: {', '.join(top[: min(10, len(top))])}"
        f"{' ...' if len(top) > 10 else ''}"
    )
    return set(top)
