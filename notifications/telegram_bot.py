# ============================================================
# TELEGRAM BOT — ihsg-ohlcdev-bot v2
# Format alert per signal type (sama dengan ihsg-supertrend-scanner)
# ============================================================
import logging, requests
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pytz

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TIMEZONE,
    INSIDER_ALERT_WINDOW_DAYS, INSIDER_ALERT_MIN_VALUE,
    NOON_OHLCV_INTERVAL,
    INTRADAY_NOON_REQUIRE_DAILY_BIAS,
    INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA20,
    INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA50,
)

logger = logging.getLogger(__name__)
WIB    = pytz.timezone(TIMEZONE)

MAX_MSG = 3800  # Telegram limit ~4096, beri buffer


# ── Helpers ──────────────────────────────────────────────────

def _now_wib() -> str:
    return datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")

def _send(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(text); return True
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
        if r.status_code != 200:
            logger.error(f"Telegram error: {r.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def _send_chunks(lines: list):
    """Kirim pesan panjang dalam beberapa chunk jika perlu."""
    msg = ""
    for line in lines:
        if len(msg) + len(line) + 1 > MAX_MSG:
            _send(msg.strip())
            msg = ""
        msg += line + "\n"
    if msg.strip():
        _send(msg.strip())

def _format_idr(val: float) -> str:
    sign   = "+" if val >= 0 else "-"
    av     = abs(val)
    if av >= 1e12: return f"Rp{sign}{av/1e12:.2f}T"
    if av >= 1e9:  return f"Rp{sign}{av/1e9:.1f}B"
    if av >= 1e6:  return f"Rp{sign}{av/1e6:.1f}M"
    return f"Rp{sign}{av:.0f}"


def _tg_plain(s: Any, max_len: int = 120) -> str:
    """Teks aman untuk HTML Telegram (buang karakter yang memecah tag)."""
    if s is None:
        return ""
    t = str(s).replace("<", "").replace(">", "").strip()
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return t


# Field API insider-net-summary / insider-screening bervariasi — coba beberapa key umum.
_INSIDER_NAME_KEYS = (
    "insider_name", "name", "insider", "party_name", "holder_name",
    "director_name", "commissioner_name", "reporting_name",
    "shareholder_name", "person_name", "owner", "holder", "title",
    "insiderParty", "insider_party", "reportingParty", "full_name",
    "reporting_name_insider", "nama", "pemegang_saham",
)

_INSIDER_BROKER_KEYS = (
    "broker_code", "brokerCode", "netbs_broker_code", "brokerage_code",
    "buyer_broker_code", "seller_broker_code", "bbroker_code", "sbroker_code",
    "broker", "brokerage", "buyer_broker", "seller_broker",
    "broker_name", "kode_broker",
)


def _insider_row_name(row: Dict[str, Any]) -> str:
    for k in _INSIDER_NAME_KEYS:
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, dict):
            v = v.get("name") or v.get("fullName") or v.get("full_name") or v.get("code")
        s = _tg_plain(v, 100)
        if s and s.upper() not in ("BUY", "SELL", "NULL", "NONE", "-"):
            return s
    return ""


def _insider_row_broker(row: Dict[str, Any]) -> str:
    for k in _INSIDER_BROKER_KEYS:
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, dict):
            inner = v.get("code") or v.get("broker_code") or v.get("name")
            s = _tg_plain(inner, 32)
            if s:
                return s.upper() if len(s) <= 6 else s
            continue
        s = _tg_plain(v, 32)
        if s:
            return s.upper() if len(s) <= 6 else s
    for side in ("buyer", "seller", "buyerCode", "sellerCode"):
        v = row.get(side)
        if not isinstance(v, str):
            continue
        u = v.strip().upper()
        if 2 <= len(u) <= 10 and u.replace(".", "").isalnum() and u not in ("BUY", "SELL"):
            return u
    return ""


def _format_insider_row_html(row: Dict[str, Any]) -> str:
    """Satu baris insider: simbol, nama pelapor, kode broker, tipe, nilai/lot."""
    sym = (
        row.get("symbol")
        or row.get("ticker")
        or row.get("code")
        or row.get("stock_code")
        or row.get("stockCode")
        or row.get("emiten")
        or row.get("security_code")
        or "?"
    )
    if isinstance(sym, str):
        sym = sym.strip().upper()
    name = _insider_row_name(row)
    brk = _insider_row_broker(row)
    typ = row.get("type", row.get("transaction_type", row.get("side", "")))
    amt = row.get(
        "amount",
        row.get("value", row.get("lot", row.get("qty", row.get("volume", "")))),
    )
    icon = "[+]" if "BUY" in str(typ).upper() else "[-]"
    bits = [f"  {icon} <b>{_tg_plain(str(sym), 12)}</b>"]
    if name:
        bits.append(f"| {_tg_plain(name, 100)}")
    if brk:
        bits.append(f"| br {_tg_plain(brk, 32)}")
    bits.append(f"| {_tg_plain(str(typ), 24)} {_tg_plain(str(amt), 40)}".rstrip())
    return " ".join(bits)


def _insider_brief_preview(rows: List[Dict[str, Any]], limit: int = 8) -> str:
    """Ringkas untuk header brief: TICKER (nama singkat)."""
    parts = []
    for t in rows[:limit]:
        sym = (
            t.get("symbol")
            or t.get("ticker")
            or t.get("code")
            or t.get("emiten")
            or "?"
        )
        sym = str(sym).strip().upper()
        nm = _insider_row_name(t)
        if nm:
            short = nm if len(nm) <= 22 else nm[:19] + "…"
            parts.append(f"{sym} ({short})")
        else:
            parts.append(sym)
    return ", ".join(parts)


def _parse_insider_date(row: Dict[str, Any]) -> Optional[datetime]:
    v = row.get("dateObj") or row.get("date")
    if not v:
        return None
    # ISO format
    try:
        s = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        pass
    # Example: "04 May 26"
    try:
        return datetime.strptime(str(v), "%d %b %y")
    except Exception:
        return None


def _insider_estimated_value(row: Dict[str, Any]) -> float:
    """Estimasi nilai transaksi insider (IDR)."""
    try:
        ev = float(row.get("estimatedValue", 0) or 0)
    except Exception:
        ev = 0.0
    if ev > 0:
        return ev
    # Fallback: abs(change_shares) * price
    try:
        shares = abs(float(row.get("changesShares", 0) or 0))
        price = float(row.get("price", 0) or 0)
        return shares * price if shares > 0 and price > 0 else 0.0
    except Exception:
        return 0.0


def _insider_signed_value(row: Dict[str, Any]) -> float:
    """
    Nilai transaksi insider dengan sign aksi:
    BUY => positif, SELL => negatif.
    """
    val = float(_insider_estimated_value(row) or 0.0)
    act = str(row.get("actionType") or row.get("type") or row.get("transaction_type") or "").strip().upper()
    if act == "SELL":
        return -abs(val)
    if act == "BUY":
        return abs(val)
    return val


def _filter_insider_alert_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ambil insider rows yang:
    1) dalam window 7 hari,
    2) transaksi individual cukup besar,
    3) emiten punya net buy (value) positif di window tsb.
    """
    if not rows:
        return []
    parsed = []
    latest_dt = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        dt = _parse_insider_date(r)
        val = _insider_estimated_value(r)
        sym = str(r.get("symbol") or "").strip().upper()
        act = str(r.get("actionType") or "").strip().upper()
        if not sym or not dt:
            continue
        parsed.append((r, sym, act, dt, val))
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
    if not parsed or latest_dt is None:
        return []

    cutoff = latest_dt - timedelta(days=INSIDER_ALERT_WINDOW_DAYS)
    recent = [x for x in parsed if x[3] >= cutoff]
    if not recent:
        return []

    # Net value per symbol dalam window.
    net_by_symbol: Dict[str, float] = {}
    for _, sym, act, _, val in recent:
        sign = 1.0 if act == "BUY" else (-1.0 if act == "SELL" else 0.0)
        net_by_symbol[sym] = net_by_symbol.get(sym, 0.0) + (val * sign)

    # Kandidat final: transaksi besar + symbol net buy positif
    out: List[Dict[str, Any]] = []
    for row, sym, _, _, val in recent:
        if val < INSIDER_ALERT_MIN_VALUE:
            continue
        if net_by_symbol.get(sym, 0.0) <= 0:
            continue
        row2 = dict(row)
        row2["_alert_value"] = val
        row2["_symbol_net_7d"] = net_by_symbol.get(sym, 0.0)
        out.append(row2)

    out.sort(key=lambda x: float(x.get("_alert_value", 0) or 0), reverse=True)
    return out


def _filter_insider_today_big_value(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Khusus alert Insider Trading:
    - hanya tanggal terbaru (hari ini pada data feed),
    - aksi BUY/SELL (keduanya),
    - nilai transaksi >= threshold.
    """
    if not rows:
        return []
    parsed = []
    latest_dt = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        dt = _parse_insider_date(r)
        if not dt:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
        parsed.append((r, dt))
    if not parsed or latest_dt is None:
        return []

    latest_day = latest_dt.date()
    out = []
    for row, dt in parsed:
        if dt.date() != latest_day:
            continue
        act = str(row.get("actionType") or row.get("type") or "").strip().upper()
        if act not in ("BUY", "SELL"):
            continue
        val = _insider_estimated_value(row)
        if val < float(INSIDER_ALERT_MIN_VALUE):
            continue
        row2 = dict(row)
        row2["_alert_value"] = val
        out.append(row2)
    out.sort(key=lambda x: float(x.get("_alert_value", 0) or 0), reverse=True)
    return out


def _parse_event_date_any(s: Any) -> Optional[datetime]:
    if not s:
        return None
    raw = str(s).strip()
    if not raw:
        return None
    # YYYY-MM-DD / ISO
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        pass
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except Exception:
        return None


def _freq_icon(signal: str) -> str:
    return ""

def _foreign_icon(direction: str) -> str:
    return {"BUYING":"[+]","SELLING":"[-]"}.get(direction, "[ ]")

def _tp_lines(r) -> str:
    lines = []
    if r.tp1 > 0:
        pct = (r.tp1 - r.current_price) / r.current_price * 100
        lines.append(f"   TP1: {r.tp1:,.0f} (+{pct:.1f}%)")
    if r.tp2 > 0:
        pct = (r.tp2 - r.current_price) / r.current_price * 100
        src = "resist" if r.tp2_source == "RESISTANCE" else "ATR"
        lines.append(f"   TP2: {r.tp2:,.0f} (+{pct:.1f}%) {src}")
    sl = r.current_price * 0.95
    lines.append(f"   SL: {sl:,.0f} (-5.0%)")
    return "\n".join(lines)


def _tp_lines_clean(r) -> list:
    """TP/SL ringkas untuk format alert clean."""
    lines = []
    if r.tp1 > 0:
        pct = (r.tp1 - r.current_price) / r.current_price * 100
        lines.append(f"   🎯 TP1: {r.tp1:,.0f} (+{pct:.1f}%)")
    if r.tp2 > 0:
        pct = (r.tp2 - r.current_price) / r.current_price * 100
        src = "resist" if r.tp2_source == "RESISTANCE" else "ATR"
        lines.append(f"   🚀 TP2: {r.tp2:,.0f} (+{pct:.1f}%) {src}")
    sl = r.current_price * 0.95
    lines.append(f"   🛑 SL: {sl:,.0f} (-5.0%)")
    return lines


def _flow_lines_clean(r) -> list:
    """Ringkas flow penting (broksum, non-retail, asing, notes) untuk alert clean."""
    lines = []
    bd = r.bandro
    if not bd:
        return lines

    n_buy = int(getattr(bd, "broksum_total_buyer", 0) or 0)
    n_sell = int(getattr(bd, "broksum_total_seller", 0) or 0)
    if n_buy > 0 or n_sell > 0:
        lines.append(f"   🧾 Broksum: buyer {n_buy} vs seller {n_sell}")
    buyers = getattr(bd, "broksum_top_buyers", []) or []
    sellers = getattr(bd, "broksum_top_sellers", []) or []
    if buyers:
        def _bc(x):
            return x.get("code") or x.get("netbs_broker_code") or "?"
        def _bv(x):
            return float(x.get("net", x.get("bval", 0)) or 0)
        buy_txt = " | ".join(f"{_bc(b)} {_format_idr(_bv(b))}" for b in buyers[:3])
        lines.append(f"   🛒 Top buyer: {buy_txt}")
    if sellers:
        def _sc(x):
            return x.get("code") or x.get("netbs_broker_code") or "?"
        def _sv(x):
            return float(x.get("net", x.get("sval", 0)) or 0)
        sell_txt = " | ".join(f"{_sc(s)} {_format_idr(_sv(s))}" for s in sellers[:3])
        lines.append(f"   🧺 Top seller: {sell_txt}")

    nr_pct = float(getattr(bd, "broksum_non_retail_buy_pct", 0) or 0)
    loc_pct = float(getattr(bd, "broksum_lokal_buy_pct", 0) or 0)
    nr_net = float(getattr(bd, "broksum_non_retail_net", 0) or 0)
    grand_total = float(getattr(bd, "broksum_bandar_grand_total", 0) or 0)
    nr_net_pct = (nr_net / grand_total * 100.0) if grand_total > 0 else 0.0
    net_txt = f"{_format_idr(nr_net)} ({nr_net_pct:+.1f}%)" if grand_total > 0 else _format_idr(nr_net)
    if nr_pct != 0 or loc_pct != 0 or nr_net != 0:
        lines.append(
            f"   🏦 Non-retail: {nr_pct:.1f}% | Lokal: {loc_pct:.1f}% | Net: {net_txt}"
        )

    if bd.foreign_dir != "NEUTRAL" and bd.foreign_net_buy != 0:
        lines.append(f"   🌍 Asing: {bd.foreign_dir} {_format_idr(bd.foreign_net_buy)}")

    notes = []
    if bd.freq_signal in ("WHALE", "HIGH_LOT"):
        notes.append(bd.freq_signal)
    if bd.is_accumulating and bd.accum_signal == "STRONG_ACCUMULATION":
        notes.append("Akumulasi kuat")
    if notes:
        lines.append(f"   💡 Note: {' | '.join(notes)}")

    return lines

def _buyer_seller_line(r) -> str:
    """
    Baris standar frekuensi buyer vs seller (broker summary 1D).
    Dipakai di semua jenis alert teknikal agar konsisten.
    """
    bd = r.bandro
    if not bd or not getattr(bd, "has_broksum", False):
        return ""
    n_buy = int(getattr(bd, "broksum_total_buyer", 0) or 0)
    n_sell = int(getattr(bd, "broksum_total_seller", 0) or 0)
    if n_buy == 0 and n_sell == 0:
        return ""
    return f"   Broksum: buyer {n_buy} vs seller {n_sell}"


def _non_retail_flow_line(r) -> str:
    """
    Indikator non-retail-flow: % nilai beli dari investor Asing+Pemerintah,
    banding lokal, dan net gabungan non-retail hari ini (dari API broksum).
    """
    bd = r.bandro
    if not bd or not getattr(bd, "has_broksum", False):
        return ""
    nr_pct = float(getattr(bd, "broksum_non_retail_buy_pct", 0) or 0)
    loc_pct = float(getattr(bd, "broksum_lokal_buy_pct", 0) or 0)
    nr_net = float(getattr(bd, "broksum_non_retail_net", 0) or 0)
    if nr_pct == 0 and loc_pct == 0 and nr_net == 0:
        return ""
    return (
        f"   non-retail-flow: {nr_pct:.1f}% nilai beli (Asing+Pemerintah) | "
        f"lokal {loc_pct:.1f}% | net non-retail {_format_idr(nr_net)}"
    )


def _bandar_day_line(r) -> str:
    """
    Ringkasan konsentrasi bandar hari itu dari broker summary.

    Metrik baru (fix):
      pct = total_beli_semua_broker / total_transaksi_harian * 100
    Bukan net/total (yang selalu ~0%), tapi seberapa terkonsentrasi
    aksi beli di sisi broker.

    Contoh output:
      Bandar [ALL]: Konsentrasi 14.9% beli | Rp67.0M → Rp448.6M | buyer 22 vs seller 17
    """
    bd = r.bandro
    if not bd or not getattr(bd, "has_broksum", False):
        return ""
    sig         = getattr(bd, "broksum_bandar", "NEUTRAL")
    amt         = float(getattr(bd, "broksum_bandar_amount", 0.0) or 0.0)   # total beli
    pct         = float(getattr(bd, "broksum_bandar_percent", 0.0) or 0.0)  # % beli dari grand total
    grand_total = float(getattr(bd, "broksum_bandar_grand_total", 0.0) or 0.0)  # buy + abs(sell)
    source      = str(getattr(bd, "broksum_bandar_source", "") or "").upper()

    src_txt = f" [{source}]" if source else ""

    # Label konsentrasi beli vs total transaksi dua sisi (bukan opini "bandar")
    label_map = {
        "BIG_ACC": "beli 40%+ dr total transaksi",
        "ACC":     "beli 25-40% dr total transaksi",
        "WATCH":   "beli 10-25% dr total transaksi",
        "NEUTRAL": "beli di bawah 10% dr total transaksi",
    }
    label = label_map.get(sig, sig.title() if sig else "")

    # Baris utama: angka nyata + klasifikasi rentang
    if pct > 0:
        main = f"   Konsentrasi beli{src_txt}: {pct:.1f}% ({label})"
    else:
        main = f"   Konsentrasi beli{src_txt}: ({label})"

    # Detail: nilai beli dari grand total (buy+sell dua sisi)
    if grand_total > 0 and amt > 0:
        flow_txt = f"{_format_idr(amt)} / {_format_idr(grand_total)}"
    elif amt > 0:
        flow_txt = f"beli {_format_idr(amt)}"
    else:
        flow_txt = ""

    extras = " | ".join(x for x in [flow_txt] if x)
    return main + (f" | {extras}" if extras else "")


def _frequency_line(r) -> str:
    """Baris ringkas frequency analyzer."""
    fr = float(getattr(r, "frequency_ratio", 1.0) or 1.0)
    fs = int(getattr(r, "frequency_strength", 0) or 0)
    recent_max = float(getattr(r, "frequency_recent_max", 1.0) or 1.0)
    recent_spikes = int(getattr(r, "frequency_recent_spike_count", 0) or 0)
    if fr < 2.0 and recent_spikes <= 0 and not getattr(r, "is_frequency_analyzer", False):
        return ""
    tag = "Surge" if fr >= 3 else ("Spike" if fr >= 2 else "Rising")
    vol_hint = "vol kecil" if getattr(r, "frequency_stealth_volume_ok", False) else "vol besar"
    return f"   Freq: {tag} {fr:.1f}x | {vol_hint} | setup {recent_spikes}h | S{fs}/9"

def _broksum_line(r) -> str:
    """Broker summary 1D (Ultra): top buyers & sellers net."""
    bd = r.bandro
    if not bd or not getattr(bd, "has_broksum", False):
        return ""
    buyers = getattr(bd, "broksum_top_buyers", []) or []
    sellers = getattr(bd, "broksum_top_sellers", []) or []
    if not buyers and not sellers:
        return ""

    def _bc(x):
        return x.get("code") or x.get("netbs_broker_code") or "?"

    def _bv(x):
        return float(x.get("net", x.get("bval", 0)) or 0)

    def _sv(x):
        return float(x.get("net", x.get("sval", 0)) or 0)

    buy_txt = " | ".join(f"{_bc(b)} {_format_idr(_bv(b))}" for b in buyers[:2]) if buyers else "-"
    sell_txt = " | ".join(f"{_bc(s)} {_format_idr(_sv(s))}" for s in sellers[:2]) if sellers else "-"
    dom = getattr(bd, "broksum_dominant", "NEUTRAL")
    icon = "[+]" if dom == "BUYING" else ("[-]" if dom == "SELLING" else "[ ]")
    dt = getattr(bd, "broksum_date", "")
    suffix = f" ({dt})" if dt else ""
    return f"   Broksum {icon}: B {buy_txt} | S {sell_txt}{suffix}"

def _foreign_line(r) -> str:
    """Baris ringkas foreign flow."""
    bd = r.bandro
    if not bd or bd.foreign_dir == "NEUTRAL" or bd.foreign_net_buy == 0:
        return ""
    icon = _foreign_icon(bd.foreign_dir)
    return f"   Asing {icon}: {_format_idr(bd.foreign_net_buy)} (1D)"

def _enrich_tags(r) -> list:
    """Tag tambahan HIGH CONVICTION / Whale / Bandar."""
    tags = []
    bd   = r.bandro
    if bd:
        if bd.freq_signal in ("WHALE", "HIGH_LOT"):
            tags.append(f"   Note: {bd.freq_signal}")
        if bd.is_accumulating and bd.accum_signal == "STRONG_ACCUMULATION":
            tags.append("   Note: Akumulasi kuat")
    return tags


# ── Format per signal type ────────────────────────────────────

def _fmt_stock(r, prefix: str = "-") -> list:
    """Format satu saham menjadi list baris."""
    sr  = r.score_result
    chg = f"+{r.change_pct:.1f}%" if r.change_pct >= 0 else f"{r.change_pct:.1f}%"
    lines = [
        f"{prefix} <b>{r.symbol}</b> | {r.current_price:,.0f} ({chg})",
        f"   Score {sr.total_score} | MACD {r.macd_status} | Vol {r.volume_ratio:.1f}x",
    ]
    bvs = _buyer_seller_line(r)
    if bvs:
        lines.append(bvs)
    nrf = _non_retail_flow_line(r)
    if nrf:
        lines.append(nrf)
    fl2 = _frequency_line(r)
    if fl2 and getattr(r, "is_frequency_analyzer", False):
        lines.append(fl2)
    # Inti flow: freq (jika FA), bandar, asing, broksum ringkas
    bsl = _broksum_line(r)
    fl = _foreign_line(r)
    if fl: lines.append(fl)
    if bsl: lines.append(bsl)
    # Extra tags
    lines.extend(_enrich_tags(r))
    # TP/SL
    lines.append(_tp_lines(r))
    lines.append("")
    return lines


def send_strong_buy(results: list):
    if not results: return
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>🚀 STRONG BUY SIGNAL</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
        "",
    ]
    for r in results:
        sr = r.score_result
        chg = f"+{r.change_pct:.1f}%" if r.change_pct >= 0 else f"{r.change_pct:.1f}%"
        lines += [
            f"🟢 <b>{r.symbol}</b> | {r.current_price:,.0f} ({chg})",
            f"   └ Score: {sr.total_score} | MACD: {r.macd_status} | Vol: {r.volume_ratio:.1f}x",
        ]
        lines.extend(_flow_lines_clean(r))
        lines.extend(_tp_lines_clean(r))
        lines.append("")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Breakout terkonfirmasi + score ≥ 70",
        f"Total: {len(results)} saham strong buy",
    ]
    _send_chunks(lines)


def send_accumulation(results: list):
    if not results: return
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>🔵 ACCUMULATION SIGNAL</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
        "",
    ]
    for r in results:
        sr = r.score_result
        chg = f"+{r.change_pct:.1f}%" if r.change_pct >= 0 else f"{r.change_pct:.1f}%"
        lines += [
            f"📊 <b>{r.symbol}</b> | {r.current_price:,.0f} ({chg})",
            f"   └ Score: {sr.total_score} | OBV: {r.obv_status} | Vol: {r.volume_ratio:.1f}x",
        ]
        lines.extend(_flow_lines_clean(r))
        lines.extend(_tp_lines_clean(r))
        lines.append("")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Total: {len(results)} saham accumulation",
    ]
    _send_chunks(lines)


def send_bull_div(results: list):
    if not results: return
    strong   = [r for r in results if r.div_grade == "STRONG"]
    moderate = [r for r in results if r.div_grade == "MODERATE"]
    weak     = [r for r in results if r.div_grade == "WEAK"]

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>↩️ BULLISH DIVERGENCE SIGNAL</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
        "",
    ]
    for grade, group, icon in [("STRONG", strong, "🟩"),
                               ("MODERATE", moderate, "🟨"),
                               ("WEAK", weak, "🟧")]:
        if group:
            lines.append(f"{icon} <b>{grade}</b>")
            for r in group:
                sr = r.score_result
                chg = f"+{r.change_pct:.1f}%" if r.change_pct >= 0 else f"{r.change_pct:.1f}%"
                lines += [
                    f"↩️ <b>{r.symbol}</b> | {r.current_price:,.0f} ({chg})",
                    f"   └ Score: {sr.total_score} | Div: {r.div_grade} | Strength: {r.div_strength}",
                ]
                lines.extend(_flow_lines_clean(r))
                lines.extend(_tp_lines_clean(r))
                lines.append("")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Pivot low + RSI higher low = potensi reversal",
        f"Total: {len(results)} ({len(strong)} strong, {len(moderate)} moderate, {len(weak)} weak)",
    ]
    _send_chunks(lines)


def send_early_entry(results: list):
    if not results: return
    sorted_r = sorted(results, key=lambda r: r.early_strength, reverse=True)
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>🎯 EARLY ENTRY SIGNAL</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
        "",
    ]
    for r in sorted_r:
        prefix = "🟢" if r.early_strength >= 5 else ("🟡" if r.early_strength >= 3 else "🟠")
        sr    = r.score_result
        chg   = f"+{r.change_pct:.1f}%" if r.change_pct >= 0 else f"{r.change_pct:.1f}%"
        lines += [
            f"{prefix} <b>{r.symbol}</b> | {r.current_price:,.0f} ({chg})",
            f"   └ Koreksi: {r.correction_pct:.1f}% | Strength: {r.early_strength}/7 | Score: {sr.total_score}",
        ]
        lines.extend(_flow_lines_clean(r))
        lines.extend(_tp_lines_clean(r))
        lines.append("")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Sinyal dini — DYOR!",
        f"Total: {len(results)} saham early entry",
    ]
    _send_chunks(lines)


def send_frequency_analyzer(results: list):
    if not results:
        return
    sorted_r = sorted(results, key=lambda r: (getattr(r, "flow_score", 0), getattr(r, "frequency_ratio", 1.0)), reverse=True)
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>⚡ FREQ ANALYZER SPIKE</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
        "",
    ]
    for r in sorted_r:
        chg = f"+{r.change_pct:.1f}%" if r.change_pct >= 0 else f"{r.change_pct:.1f}%"
        stage = getattr(r, "flow_stage", "EARLY_SETUP") or "EARLY_SETUP"
        lines += [
            f"⚡ <b>{r.symbol}</b> | {r.current_price:,.0f} ({chg})",
            f"   └ Flow Score: {getattr(r, 'flow_score', 0)} | Stage: {stage} | Freq: {r.frequency_ratio:.1f}x",
        ]
        lines.extend(_flow_lines_clean(r))
        lines.extend(_tp_lines_clean(r))
        lines.append("")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Transaction-first early setup (sebelum markup)",
        f"Total: {len(results)} saham freq analyzer spike",
    ]
    _send_chunks(lines)


def send_all_signals(signals: Dict[str, list]):
    """Kirim semua tipe sinyal yang ada."""
    sent = 0
    if signals.get("strong_buy"):
        send_strong_buy(signals["strong_buy"]); sent += 1
    if signals.get("accumulation"):
        send_accumulation(signals["accumulation"]); sent += 1
    if signals.get("bull_div"):
        send_bull_div(signals["bull_div"]); sent += 1
    if signals.get("early_entry"):
        send_early_entry(signals["early_entry"]); sent += 1
    if signals.get("frequency_analyzer"):
        send_frequency_analyzer(signals["frequency_analyzer"]); sent += 1
    return sent


# ── Morning brief ─────────────────────────────────────────────

def _format_screening_extras(engine_results: Optional[dict]) -> str:
    """Ringkas insider (Engine 4) + agenda RUPS/RI/SS/dividen (Engine 6) untuk header brief."""
    if not engine_results:
        return ""
    lines = ["", "<b>Insider + agenda</b>"]
    insider = engine_results.get("insider")
    if insider and getattr(insider, "available", False) and insider.all_insider:
        rows = insider.all_insider
        preview = _insider_brief_preview(rows, limit=8)
        lines.append(f"  Insider (laporan): {len(rows)} — {preview}")
    else:
        lines.append("  Insider: (tidak ada data / belum tersedia)")

    ev = engine_results.get("events")
    if ev and getattr(ev, "available", False):
        lines.append(
            "  Kalender: "
            f"dividen {len(ev.dividends or [])} | "
            f"RUPS {len(ev.rups or [])} | "
            f"RI {len(ev.rights_issue or [])} | "
            f"SS {len(ev.stock_split or [])}"
        )
    else:
        lines.append("  Kalender: (tidak ada data / belum tersedia)")

    return "\n".join(lines)


def _format_macro(macro: Optional[dict], signals: Optional[Dict[str, list]] = None) -> str:
    if not macro:
        return ""
    def _to_float(v, default=0.0):
        try:
            if v is None:
                return default
            s = str(v).replace(",", "").replace("%", "").strip()
            return float(s)
        except Exception:
            return default

    def _pick(d: dict, keys: list, default=None):
        for k in keys:
            if isinstance(d, dict) and k in d and d.get(k) is not None:
                return d.get(k)
        return default

    lines = ["\n<b>📊 Makro Pagi (Insight)</b>"]
    urgent = []
    watchlist = []
    impact_map: Dict[str, set] = {}

    # Kumpulan simbol yang memang lolos screening teknikal (agar mapping lebih actionable).
    signal_symbols = set()
    if isinstance(signals, dict):
        for key in ("strong_buy", "accumulation", "early_entry", "frequency_analyzer", "bull_div"):
            for r in signals.get(key, []) or []:
                s = str(getattr(r, "symbol", "") or "").strip().upper()
                if s:
                    signal_symbols.add(s)

    briefing = macro.get("briefing")
    if briefing and isinstance(briefing, dict):
        outlook = briefing.get("outlook") or briefing.get("summary") or briefing.get("message") or ""
        if outlook:
            lines.append(f"  📋 Outlook: {str(outlook)[:220]}")

        # Prioritaskan indeks global yang dampaknya paling besar.
        idx = briefing.get("globalIndices") or briefing.get("indices") or []
        if isinstance(idx, list) and idx:
            ranked = []
            for x in idx:
                if not isinstance(x, dict):
                    continue
                name = str(x.get("name") or x.get("symbol") or "").strip()
                chg = _to_float(x.get("changePercent", x.get("change_pct", x.get("change"))), 0.0)
                if name:
                    ranked.append((name, chg))
            ranked.sort(key=lambda t: abs(t[1]), reverse=True)
            if ranked:
                top = ranked[:3]
                # Wajib tampilkan Nikkei jika tersedia (karena relevan untuk sesi Asia).
                nikkei = next((x for x in ranked if "nikkei" in x[0].lower()), None)
                if nikkei and nikkei not in top:
                    top = top + [nikkei]
                idx_txt = " | ".join(f"{n} {c:+.2f}%" for n, c in top)
                lines.append(f"  🌐 Global: {idx_txt}")
                if any(c <= -1.0 for _, c in top):
                    urgent.append("Tekanan global negatif kuat (>=1% turun) → kurangi entry agresif.")
                    urgent.append("Hindari sementara emiten high-beta/cyclical sampai tekanan global mereda.")
                elif all(c >= 0.5 for _, c in top):
                    watchlist.append("Global risk-on mendukung momentum breakout jangka pendek.")

    forex = macro.get("forex")
    if forex and isinstance(forex, dict):
        fx = forex.get("forex", forex) if isinstance(forex.get("forex", forex), dict) else forex
        usd = _to_float(_pick(fx, ["price", "rate", "usd_idr"], 0), 0.0)
        fx_chg = _to_float(_pick(fx, ["changePercent", "change_pct", "change"], 0), 0.0)
        if usd > 0:
            lines.append(f"  💵 USD/IDR: {usd:,.0f} ({fx_chg:+.2f}%)")
        if fx_chg >= 0.5:
            urgent.append("Rupiah melemah cukup cepat → sensitif untuk emiten importir/berutang USD.")
        elif fx_chg <= -0.5:
            watchlist.append("Rupiah menguat signifikan → ruang napas untuk emiten importir.")

        benef = forex.get("beneficiaries", {}) if isinstance(forex.get("beneficiaries", {}), dict) else {}
        hurt = forex.get("vulnerable", {}) if isinstance(forex.get("vulnerable", {}), dict) else {}
        b_secs = benef.get("sectors") if isinstance(benef, dict) else None
        h_secs = hurt.get("sectors") if isinstance(hurt, dict) else None
        if isinstance(b_secs, list) and b_secs:
            lines.append("  ✅ Diuntungkan FX: " + ", ".join(str(x) for x in b_secs[:3]))
        if isinstance(h_secs, list) and h_secs:
            lines.append("  ⚠️ Tertekan FX: " + ", ".join(str(x) for x in h_secs[:3]))
        # Endpoint ini mengembalikan emiten beneficiaries (importers/exporters).
        if isinstance(benef, dict):
            exporters = benef.get("exporters")
            importers = benef.get("importers")
            if isinstance(exporters, list) and exporters:
                impact_map.setdefault("FX Beneficiary", set()).update(str(x).upper() for x in exporters if x)
            if isinstance(importers, list) and importers:
                impact_map.setdefault("FX Pressure", set()).update(str(x).upper() for x in importers if x)

    comm = macro.get("commodities")
    if comm and isinstance(comm, dict):
        items = comm.get("commodities") or comm.get("items") or comm.get("data") or []
        if isinstance(items, list) and items:
            parsed = []
            for row in items:
                if not isinstance(row, dict):
                    continue
                c = row.get("commodity", row) if isinstance(row.get("commodity", row), dict) else row
                name = str(c.get("name") or c.get("symbol") or "").strip()
                price = _to_float(c.get("price", c.get("value", 0)), 0.0)
                currency = str(c.get("currency") or "USD").upper()
                chg = _to_float(c.get("changePercent", c.get("change_pct", c.get("change"))), 0.0)
                impact = str(row.get("impact") or "").lower()
                rel = row.get("relatedStocks", [])
                if name:
                    parsed.append((name, price, currency, chg, impact, rel))
            parsed.sort(key=lambda t: abs(t[1]), reverse=True)
            if parsed:
                def _fmt_price(px: float, ccy: str) -> str:
                    if px <= 0:
                        return ""
                    prefix = "$" if "USD" in ccy else ""
                    return f"{prefix}{px:,.2f}"

                lines.append(
                    "  🛢️ Komoditas: " + " | ".join(
                        f"{n} {_fmt_price(px, ccy)} ({chg:+.2f}%)".strip()
                        for n, px, ccy, chg, _, _ in parsed[:3]
                    )
                )
                for name, _, _, chg, impact, rel in parsed[:3]:
                    up = chg >= 2.0
                    down = chg <= -2.0
                    n = name.lower()
                    if ("oil" in n or "crude" in n) and up:
                        urgent.append("Minyak naik tajam → risiko biaya/tekanan margin sektor pengguna energi.")
                    if ("oil" in n or "crude" in n) and down:
                        watchlist.append("Minyak turun tajam → potensi relief biaya untuk sektor konsumsi/logistik.")
                    if "coal" in n and up:
                        watchlist.append("Batu bara menguat → sentimen dukung emiten batu bara.")
                    if "cpo" in n and up:
                        watchlist.append("CPO menguat → sentimen positif untuk emiten CPO.")
                if isinstance(rel, list) and rel:
                    theme = "Commodity Watch"
                    if impact == "positive":
                        theme = "Commodity Beneficiary"
                    elif impact == "negative":
                        theme = "Commodity Pressure"
                    impact_map.setdefault(theme, set()).update(str(x).upper() for x in rel if x)

    if urgent:
        lines.append("  🚨 Urgent:")
        for u in urgent[:3]:
            lines.append(f"    - {u}")
    if watchlist:
        lines.append("  👀 Watchlist:")
        for w in watchlist[:3]:
            lines.append(f"    - {w}")

    # Mapping emiten terdampak: prioritaskan yang juga muncul di signal hari ini.
    if impact_map:
        lines.append("  🎯 Emiten Terdampak:")
        for theme, symbols in list(impact_map.items())[:4]:
            ordered = sorted(symbols)
            if signal_symbols:
                hit = [s for s in ordered if s in signal_symbols]
                rest = [s for s in ordered if s not in signal_symbols]
                picks = (hit[:4] + rest[:2])[:6]
            else:
                picks = ordered[:6]
            if picks:
                # Tambahkan penanda jika termasuk hasil screening teknikal.
                if signal_symbols:
                    disp = [f"{s}*" if s in signal_symbols else s for s in picks]
                    lines.append(f"    - {theme}: {', '.join(disp)}")
                else:
                    lines.append(f"    - {theme}: {', '.join(picks)}")
        pressure_symbols = sorted(impact_map.get("FX Pressure", set()) | impact_map.get("Commodity Pressure", set()))
        if pressure_symbols:
            lines.append(f"    - ⚠️ Hindari dulu: {', '.join(pressure_symbols[:6])}")
        if signal_symbols:
            lines.append("    * termasuk kandidat dari hasil sinyal teknikal pagi ini")

    return "\n".join(lines) if len(lines) > 1 else ""


def send_morning_brief(
    signals: Dict[str, list],
    macro: Optional[dict] = None,
    engine_results: Optional[dict] = None,
):
    """Sesi pagi 08:00 — makro + ringkasan screening (teknikal + insider + agenda)."""
    total = sum(len(v) for v in signals.values())
    macro_str = _format_macro(macro, signals=signals)
    extras = _format_screening_extras(engine_results)

    n_sb  = len(signals.get("strong_buy", []))
    n_acc = len(signals.get("accumulation", []))
    n_div = len(signals.get("bull_div", []))
    n_ee  = len(signals.get("early_entry", []))
    n_fa  = len(signals.get("frequency_analyzer", []))

    header = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>🌅 MORNING BRIEF — IDX</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
    ]
    if macro_str:
        header.append(macro_str)
    header += [
        "",
        "<b>Sinyal teknikal</b>",
        f"  - Strong Buy  : {n_sb}",
        f"  - Accumulation: {n_acc}",
        f"  - Bull Div    : {n_div}",
        f"  - Early Entry : {n_ee}",
        f"  - Freq Spike  : {n_fa}",
        f"  Total         : {total}",
    ]
    if extras:
        header.append(extras)
    header += ["", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    _send_chunks(header)

    # Kirim detail sinyal teknikal
    if total > 0:
        send_all_signals(signals)


def send_evening_report(
    signals: Dict[str, list],
    engine_results: Optional[dict] = None,
):
    """Sesi malam — full scan teknikal + ringkasan insider & agenda."""
    total = sum(len(v) for v in signals.values())
    extras = _format_screening_extras(engine_results)

    header = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>🌆 EVENING SCAN — IDX</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
        "",
        "<b>Sinyal teknikal</b>",
        f"  - Strong Buy  : {len(signals.get('strong_buy', []))}",
        f"  - Accumulation: {len(signals.get('accumulation', []))}",
        f"  - Bull Div    : {len(signals.get('bull_div', []))}",
        f"  - Early Entry : {len(signals.get('early_entry', []))}",
        f"  - Freq Spike  : {len(signals.get('frequency_analyzer', []))}",
        f"  Total         : {total}",
    ]
    if extras:
        header.append(extras)
    header.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    _send_chunks(header)

    if total > 0:
        send_all_signals(signals)
    else:
        _send("Tidak ada sinyal teknikal yang memenuhi kondisi hari ini.")


def send_noon_intraday_alert(signals: Dict[str, list]):
    """Sesi 12:00 — shortlist intraday sesi 2 yang masih fresh/valid."""
    total = sum(len(v) for v in signals.values())
    bias_bits = []
    if INTRADAY_NOON_REQUIRE_DAILY_BIAS:
        if INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA20:
            bias_bits.append("close daily ≥ EMA20")
        if INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA50:
            bias_bits.append("close daily ≥ EMA50")
    bias_txt = " + ".join(bias_bits) if bias_bits else "(off)"
    header = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<b>🕛 INTRADAY SESI 2 ALERT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {_now_wib()}",
        "",
        f"TF teknikal: <b>{NOON_OHLCV_INTERVAL}</b> | bias daily: <b>{bias_txt}</b>",
        "",
        "Filter:",
        "  - Belum TP1 / tidak mepet target",
        "  - Belum terlalu naik (masih ada ruang lanjut)",
        "  - Fokus kandidat lanjut sore / watchlist besok pagi",
        "",
        "<b>Sinyal teknikal terpilih</b>",
        f"  - Strong Buy  : {len(signals.get('strong_buy', []))}",
        f"  - Accumulation: {len(signals.get('accumulation', []))}",
        f"  - Bull Div    : {len(signals.get('bull_div', []))}",
        f"  - Early Entry : {len(signals.get('early_entry', []))}",
        f"  - Freq Spike  : {len(signals.get('frequency_analyzer', []))}",
        f"  Total         : {total}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    _send_chunks(header)

    if total > 0:
        send_all_signals(signals)
    else:
        _send("Tidak ada kandidat sesi 2 yang masih valid/fresh pada jam 12.")


# ── Engine Alerts (Ultra plan) ────────────────────────────────

def _sep():
    return "=" * 26


def _retail_breakout_points(row: Dict[str, Any]) -> int:
    sev = str(row.get("severity", "")).upper()
    if sev == "HIGH":
        return 28
    if sev == "MEDIUM":
        return 20
    if sev == "LOW":
        return 12
    return 16 if row else 0


def _retail_multibagger_points(score: float) -> int:
    if score >= 80:
        return 24
    if score >= 70:
        return 22
    if score >= 60:
        return 18
    if score >= 50:
        return 14
    return 8


def _retail_rr_points(rr: float) -> int:
    if rr >= 2.5:
        return 20
    if rr >= 2.0:
        return 17
    if rr >= 1.6:
        return 12
    if rr >= 1.2:
        return 8
    return 3


def _build_retail_opportunity_lines(engine_results: dict) -> List[str]:
    """Bangun section Retail Opportunity Score dari engine data + risk/reward API."""
    sweep = engine_results.get("sweep")
    bandar = engine_results.get("bandar")
    if not sweep:
        return []

    by_symbol: Dict[str, Dict[str, Any]] = {}

    for b in (sweep.breakout_stocks or []):
        if not isinstance(b, dict):
            continue
        s = str(b.get("symbol") or b.get("ticker") or b.get("code") or "").strip().upper()
        if not s:
            continue
        by_symbol.setdefault(s, {})["breakout"] = b

    for m in (sweep.multibagger or []):
        if not isinstance(m, dict):
            continue
        s = str(m.get("symbol") or m.get("ticker") or m.get("code") or "").strip().upper()
        if not s:
            continue
        by_symbol.setdefault(s, {})["multibagger"] = m

    for t in (sweep.trending or []):
        if not isinstance(t, dict):
            continue
        s = str(t.get("symbol") or t.get("ticker") or t.get("code") or "").strip().upper()
        if not s:
            continue
        by_symbol.setdefault(s, {})["trending"] = t

    if not by_symbol:
        return []

    pump_set = set()
    smart_inflow_set = set()
    if bandar:
        for p in (bandar.pump_dump or []):
            s = str((p or {}).get("symbol") or "").strip().upper()
            if s:
                pump_set.add(s)
        for sm in (bandar.smart_money or []):
            s = str((sm or {}).get("symbol") or "").strip().upper()
            if s:
                smart_inflow_set.add(s)

    # preliminary score without RR
    rows: List[Dict[str, Any]] = []
    for sym, pack in by_symbol.items():
        b = pack.get("breakout", {})
        m = pack.get("multibagger", {})
        mb_score = float(m.get("multibagger_score", 0) or 0)
        p_break = _retail_breakout_points(b)
        p_multi = _retail_multibagger_points(mb_score) if m else 0
        p_trend = 6 if pack.get("trending") else 0
        p_risk = -8 if sym in pump_set else 0
        p_flow = 6 if sym in smart_inflow_set else 0
        prelim = p_break + p_multi + p_trend + p_risk + p_flow
        rows.append({
            "symbol": sym,
            "prelim": prelim,
            "p_break": p_break,
            "p_multi": p_multi,
            "p_trend": p_trend,
            "p_risk": p_risk,
            "p_flow": p_flow,
            "multibagger_score": mb_score,
            "breakout_sev": str(b.get("severity", "")).upper() if isinstance(b, dict) else "",
        })

    rows.sort(key=lambda x: x.get("prelim", 0), reverse=True)
    top_rows = rows[:6]

    # RR fetch untuk kandidat teratas agar lebih hemat quota.
    from core.engines import fetch_risk_reward
    for r in top_rows:
        rr = fetch_risk_reward(r["symbol"]) or {}
        rr_ratio = float(rr.get("risk_reward_ratio", 0) or 0)
        rec = str(rr.get("recommendation") or "").upper()
        p_rr = _retail_rr_points(rr_ratio)
        total = r["p_break"] + r["p_multi"] + r["p_trend"] + r["p_risk"] + r["p_flow"] + p_rr
        r["rr_ratio"] = rr_ratio
        r["rr_rec"] = rec
        r["p_rr"] = p_rr
        r["score"] = max(0, min(100, int(total)))

    top_rows.sort(key=lambda x: x.get("score", 0), reverse=True)

    lines = [_sep(), "<b>RETAIL OPPORTUNITY SCORE</b>", _sep(), "⏰ " + _now_wib(), ""]
    for r in top_rows[:4]:
        sym = r["symbol"]
        score = r.get("score", 0)
        icon = "🟢" if score >= 75 else ("🟡" if score >= 60 else "🔴")
        rr_txt = f"{r.get('rr_ratio', 0):.2f}" if r.get("rr_ratio", 0) > 0 else "n/a"
        lines.append(f"{icon} {sym} | Retail Score {score}/100")
        lines.append(
            f"   └ Breakout: {r.get('breakout_sev','-') or '-'} (+{r.get('p_break',0)}) | "
            f"Multibagger: {int(r.get('multibagger_score',0))} (+{r.get('p_multi',0)})"
        )
        lines.append(
            f"   └ R:R: {rr_txt} (+{r.get('p_rr',0)}) | Trend: +{r.get('p_trend',0)} | "
            f"Flow/Risk: {r.get('p_flow',0):+d}/{r.get('p_risk',0):+d}"
        )
        if sym in pump_set:
            lines.append("   ⚠️ Pump/Dump risk terdeteksi, jangan entry agresif.")
        elif sym in smart_inflow_set:
            lines.append("   ✅ Smart money inflow mendukung setup.")
        lines.append("")
    lines.append(_sep())
    return lines


def send_engine_alerts(engine_results: dict):
    """
    Kirim alert dari non-teknikal engines.
    Key dict: sweep, bandar, insider, sector, events, whale
    Field names sesuai dataclass di core/engines.py
    Saat ini semua masih stub (butuh Ultra plan).
    """
    if not engine_results:
        return

    lines = []

    # Engine 2 — Market Sweep
    sweep = engine_results.get("sweep")
    if sweep and (sweep.top_gainers or sweep.breakout_stocks or sweep.multibagger):
        lines.extend([_sep(), "<b>MARKET SWEEP</b>", _sep(), "⏰ " + _now_wib(), ""])
        if sweep.top_gainers:
            syms = ", ".join(m.get("symbol", str(m)) for m in sweep.top_gainers[:5])
            lines.append("  - Top Gainers: " + syms)
        if sweep.breakout_stocks:
            syms = ", ".join(b.get("symbol", str(b)) for b in sweep.breakout_stocks[:5])
            lines.append("  - Breakout: " + syms)
        if sweep.multibagger:
            syms = ", ".join(m.get("symbol", str(m)) for m in sweep.multibagger[:5])
            lines.append("  - Multibagger: " + syms)
        if sweep.trending:
            syms = ", ".join(t.get("symbol", str(t)) for t in sweep.trending[:5])
            lines.append("  - Trending: " + syms)
        lines.append("")

    # Engine 3 — Bandar API
    bandar = engine_results.get("bandar")
    if bandar and (bandar.accumulation or bandar.distribution or bandar.smart_money):
        lines.extend([_sep(), "<b>BANDAR / SMART MONEY</b>", _sep(), "⏰ " + _now_wib(), ""])
        lines.append(
            "  - Coverage API: "
            f"ACC {len(bandar.accumulation)} | "
            f"DIST {len(bandar.distribution)} | "
            f"SMART {len(bandar.smart_money)} | "
            f"PUMP {len(bandar.pump_dump)}"
        )
        if bandar.accumulation:
            syms = ", ".join(x.get("symbol", str(x)) for x in bandar.accumulation[:5])
            lines.append("  - Akumulasi: " + syms)
        if bandar.distribution:
            syms = ", ".join(x.get("symbol", str(x)) for x in bandar.distribution[:5])
            lines.append("  - Distribusi: " + syms)
        if bandar.smart_money:
            syms = ", ".join(x.get("symbol", str(x)) for x in bandar.smart_money[:5])
            lines.append("  - Smart Money: " + syms)
        if bandar.pump_dump:
            syms = ", ".join(x.get("symbol", str(x)) for x in bandar.pump_dump[:5])
            lines.append("  - Pump/Dump Alert: " + syms)
        lines.append("")

    # Retail opportunity score (gabungan breakout + multibagger + RR + risk overlay).
    try:
        retail_lines = _build_retail_opportunity_lines(engine_results)
        if retail_lines:
            lines.extend(retail_lines)
            lines.append("")
    except Exception as e:
        logger.warning(f"retail opportunity format: {e}")

    # Engine 4 — Insider Trading (nama pelapor + kode broker jika ada di payload API)
    insider = engine_results.get("insider")
    if insider and insider.all_insider:
        rows = _filter_insider_today_big_value(list(insider.all_insider))
        lines.extend([_sep(), "<b>INSIDER TRADING</b>", _sep(), "⏰ " + _now_wib(), ""])
        lines.append(
            f"Filter: data terbaru hari ini | BUY/SELL | transaksi >= {_format_idr(float(INSIDER_ALERT_MIN_VALUE))}"
        )
        lines.append("")
        show = rows[:40]
        for t in show:
            if isinstance(t, dict):
                base = _format_insider_row_html(t)
                act = str(t.get("actionType") or t.get("type") or t.get("transaction_type") or "").strip().upper()
                s_val = _insider_signed_value(t)
                lines.append(
                    f"{base} | action {act or '-'} | val {_format_idr(s_val)}"
                )
            else:
                lines.append(f"  • {_tg_plain(str(t), 200)}")
        if not rows:
            lines.append("  (tidak ada transaksi insider yang lolos filter)")
        elif len(rows) > len(show):
            lines.append(f"  … +{len(rows) - len(show)} transaksi lain (total {len(rows)})")
        lines.append("")

    # Engine 5 — Sector Rotation
    sector = engine_results.get("sector")
    if sector and sector.hot_sectors:
        lines.extend([_sep(), "<b>SECTOR ROTATION</b>", _sep(), "⏰ " + _now_wib(), ""])
        if sector.hot_sectors:
            names = ", ".join(s.get("sector", str(s)) for s in sector.hot_sectors[:4])
            lines.append("  - Sektor Panas: " + names)
        if sector.hot_stocks:
            syms = ", ".join(s.get("symbol", str(s)) for s in sector.hot_stocks[:6])
            lines.append("  - Saham Pilihan: " + syms)
        lines.append("")

    # Engine 6 — Event Calendar
    event = engine_results.get("events")
    if event and (event.dividends or event.ipo or event.rights_issue or event.stock_split or event.rups):
        today = datetime.now(WIB).date()

        def _is_today_or_future(ds: Any) -> bool:
            dt = _parse_event_date_any(ds)
            return bool(dt and dt.date() >= today)

        dividends = [d for d in (event.dividends or []) if _is_today_or_future(
            d.get("ex_date") or d.get("exDate") or d.get("date")
        )]
        ipo_rows = [x for x in (event.ipo or []) if _is_today_or_future(
            x.get("listing_date") or x.get("ipo_listing_date") or x.get("date")
        )]
        rights_rows = [x for x in (event.rights_issue or []) if _is_today_or_future(
            x.get("ex_date") or x.get("rightissue_exdate") or x.get("date")
        )]
        stock_split_rows = [x for x in (event.stock_split or []) if _is_today_or_future(
            x.get("effective_date") or x.get("date") or x.get("ex_date")
        )]
        rups_rows = [x for x in (event.rups or []) if _is_today_or_future(
            x.get("meeting_date") or x.get("date")
        )]

        def _sort_by_date(rows: List[Dict[str, Any]], keys: List[str]) -> List[Dict[str, Any]]:
            def _k(r: Dict[str, Any]):
                for k in keys:
                    dt = _parse_event_date_any(r.get(k))
                    if dt:
                        return dt
                return datetime.max
            return sorted(rows, key=_k)

        dividends = _sort_by_date(dividends, ["ex_date", "exDate", "date"])[:5]
        ipo_rows = _sort_by_date(ipo_rows, ["listing_date", "ipo_listing_date", "date"])[:3]
        rights_rows = _sort_by_date(rights_rows, ["ex_date", "rightissue_exdate", "date"])[:3]
        stock_split_rows = _sort_by_date(stock_split_rows, ["effective_date", "date", "ex_date"])[:3]
        rups_rows = _sort_by_date(rups_rows, ["meeting_date", "date"])[:5]

        today_actions = []
        for a in (event.today_actions or []):
            if isinstance(a, dict):
                ds = a.get("date") or a.get("ex_date") or a.get("action_date")
                if ds:
                    if _is_today_or_future(ds):
                        today_actions.append(a)
                else:
                    # fallback: endpoint "today actions" umumnya memang hari ini
                    today_actions.append(a)
            else:
                today_actions.append(a)

        if not dividends and not ipo_rows and not rights_rows and not stock_split_rows and not rups_rows and not today_actions:
            pass
        else:
            lines.extend([_sep(), "<b>EVENT CALENDAR</b>", _sep(), "⏰ " + _now_wib(), ""])
            for d in dividends:
                sym = d.get("symbol", "")
                ex = d.get("ex_date", d.get("exDate", d.get("date", "")))
                amount = d.get("amount", d.get("dividend", ""))
                lines.append("  - " + sym + " | Ex-Date: " + str(ex) + " | " + str(amount))
            for ipo in ipo_rows:
                sym = ipo.get("symbol", ipo.get("company_symbol", ""))
                dt = ipo.get("listing_date", ipo.get("ipo_listing_date", ipo.get("date", "")))
                lines.append("  - IPO: " + sym + " listing " + str(dt))
            for r in rights_rows:
                sym = r.get("symbol", r.get("company_symbol", ""))
                dt = r.get("ex_date", r.get("rightissue_exdate", r.get("date", "")))
                lines.append("  - Rights Issue: " + sym + " ex-date " + str(dt))
            for ss in stock_split_rows:
                sym = ss.get("symbol", ss.get("company_symbol", ""))
                dt = ss.get("effective_date", ss.get("date", ss.get("ex_date", "")))
                ratio = ss.get("ratio", "")
                tail = (" | ratio " + str(ratio)) if str(ratio).strip() else ""
                lines.append("  - Stock Split: " + sym + " effective " + str(dt) + tail)
            for rp in rups_rows:
                sym = rp.get("symbol", rp.get("company_symbol", ""))
                dt = rp.get("meeting_date", rp.get("date", ""))
                title = rp.get("title", rp.get("agenda", ""))
                tail = (" | " + str(title)) if str(title).strip() else ""
                lines.append("  - RUPS: " + sym + " " + str(dt) + tail)
            if today_actions:
                syms = ", ".join(a.get("symbol", str(a)) if isinstance(a, dict) else str(a) for a in today_actions[:5])
                lines.append("  - Corp Actions: " + syms)
            lines.append("")

    # Engine 7 — Whale
    whale = engine_results.get("whale")
    if whale and whale.whale_txns:
        lines.extend([_sep(), "<b>WHALE TRANSACTIONS</b>", _sep(), "⏰ " + _now_wib(), ""])
        for t in whale.whale_txns[:5]:
            sym  = t.get("symbol", "")
            val  = t.get("value", t.get("net", 0))
            side = t.get("side", t.get("type", ""))
            icon = "[+]" if "BUY" in str(side).upper() else "[-]"
            lines.append("  " + icon + " " + sym + ": " + _format_idr(float(val)) + " (" + str(side) + ")")
        lines.append("")

    if lines:
        _send_chunks(lines)


def send_error(msg: str):
    _send("[ERROR]\n" + msg)


def send_startup_message():
    sep = "=" * 26
    _send(
        sep + "\n"
        "<b>IHSG IDX Intelligence Bot</b>\n" +
        sep + "\n"
        "⏰ " + _now_wib() + "\n\n"
        "Jadwal:\n"
        "  - 08:00 WIB — Morning Brief\n"
        "  - 12:00 WIB — Intraday Sesi 2 Alert\n"
        "  - 18:30 WIB — Evening Scan\n\n"
        "Screening:\n"
        "  - Strong Buy | Accumulation | Bull Div | Early Entry | Freq Spike\n"
        "  - Insider (Engine) | Agenda: dividen, RUPS, RI, SS\n" +
        sep
    )
