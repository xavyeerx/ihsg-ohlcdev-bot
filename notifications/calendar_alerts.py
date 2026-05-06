# ============================================================
# CALENDAR DIGEST — dividen, stock split, rights, RUPS (info baru)
# ============================================================
import json
import logging
import os
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

_SEEN_FILE = os.path.join(os.path.dirname(__file__), "..", "database", "calendar_seen.json")


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
        logger.warning(f"calendar_seen read: {e}")
    return set()


def _save_seen(seen: Set[str]) -> None:
    path = os.path.abspath(_SEEN_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ids": sorted(seen)[-2000:]}, f, indent=2)
    except Exception as e:
        logger.warning(f"calendar_seen write: {e}")


def _ev_id(prefix: str, row: Dict[str, Any]) -> str:
    parts = [
        prefix,
        str(row.get("symbol") or row.get("code") or row.get("ticker") or ""),
        str(row.get("ex_date") or row.get("exDate") or row.get("date") or row.get("meeting_date") or ""),
        str(row.get("type") or row.get("event") or row.get("title") or "")[:40],
    ]
    return "|".join(parts)


def diff_new_calendar_items(event_result) -> List[Dict[str, Any]]:
    """
    Bandingkan kalender hari ini dengan id yang sudah pernah dikirim.
    Return list {kind, row} untuk item baru.
    """
    if not event_result or not getattr(event_result, "available", False):
        return []

    path = os.path.abspath(_SEEN_FILE)
    first_bootstrap = not os.path.isfile(path)

    seen = _load_seen()
    new_items: List[Dict[str, Any]] = []
    new_ids: List[str] = []

    def _scan(prefix: str, rows: List, kind: str):
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            eid = _ev_id(prefix, row)
            if eid in seen:
                continue
            new_ids.append(eid)
            new_items.append({"kind": kind, "row": row})

    _scan("DIV", getattr(event_result, "dividends", []) or [], "dividen")
    _scan("RI", getattr(event_result, "rights_issue", []) or [], "rights_issue")
    _scan("SS", getattr(event_result, "stock_split", []) or [], "stock_split")
    _scan("RUPS", getattr(event_result, "rups", []) or [], "rups")

    if new_ids:
        seen.update(new_ids)
        _save_seen(seen)

    # Deploy pertama: isi cache tanpa spam Telegram
    if first_bootstrap and new_items:
        return []

    return new_items


def send_new_calendar_alerts(event_result) -> int:
    """Kirim Telegram jika ada entri kalender baru. Return jumlah item dikirim."""
    items = diff_new_calendar_items(event_result)
    if not items:
        return 0
    try:
        from notifications.telegram_bot import _send
        _send(format_calendar_digest_html(items))
    except Exception as e:
        logger.warning(f"calendar telegram: {e}")
    return len(items)


def format_calendar_digest_html(items: List[Dict[str, Any]]) -> str:
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>📅 KALENDER KORPORASI (info baru)</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for it in items[:25]:
        kind = it.get("kind", "")
        row = it.get("row") or {}
        sym = row.get("symbol") or row.get("code") or "?"
        extra = row.get("ex_date") or row.get("exDate") or row.get("date") or row.get("meeting_date") or ""
        amt = row.get("amount") or row.get("dividend") or row.get("ratio") or ""
        lines.append(f"• <b>{sym}</b> [{kind}] {extra} {amt}".strip())
    if len(items) > 25:
        lines.append(f"... +{len(items) - 25} lainnya")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
