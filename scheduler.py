#!/usr/bin/env python3
# ============================================================
# SCHEDULER — ihsg-ohlcdev-bot v2
# Jadwal: 08:00 (morning brief) + 12:00 (intraday sesi-2) + malam (evening scan)
# ============================================================
# Testing manual:
#   python run_morning.py
#   python run_evening.py
#
# Aktifkan jadwal otomatis: set AUTO_SCHEDULE = True
# ============================================================

import logging, time
from datetime import datetime
import pytz

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings    import (
    RATE_LIMIT_DELAY, TIMEZONE,
    MORNING_SCAN_HOUR, MORNING_SCAN_MINUTE,
    NOON_SCAN_HOUR, NOON_SCAN_MINUTE,
    EVENING_SCAN_HOUR, EVENING_SCAN_MINUTE,
    SCAN_MAX_WORKERS,
    NOON_INCLUDE_ENGINE_FRESH_ALERTS,
    NOON_TEST_MODE_IGNORE_HISTORY,
)
from config.stocks_list import resolve_scan_universe
from core.scanner       import (
    scan_symbol, filter_signals, has_any_signal, filter_intraday_session2_signals
)
from core.engines       import run_all_engines
from notifications.telegram_bot import (
    send_morning_brief, send_evening_report, send_noon_intraday_alert,
    send_engine_alerts, send_error, send_startup_message,
)
from database.state_manager import (
    load_state, save_state, update_state,
    build_prev_states, cleanup_old_symbols,
)

logger = logging.getLogger(__name__)
WIB    = pytz.timezone(TIMEZONE)

AUTO_SCHEDULE = False  # True = aktifkan jadwal otomatis


# ── Helper ───────────────────────────────────────────────────

def _now_wib():
    return datetime.now(WIB)


def _scan_all(session: str = "evening"):
    """
    Scan semua saham secara paralel.
    Returns: (results: list[ScanResult], state: dict)
    """
    universe    = resolve_scan_universe()
    state       = load_state()
    prev_states = build_prev_states(state)
    results     = []
    errors      = []
    total       = len(universe)

    logger.info(f"[{session.upper()}] Mulai scan {total} saham (Concurrent Mode)")

    import concurrent.futures

    def _process_symbol(symbol):
        try:
            return symbol, scan_symbol(symbol, prev_states, session=session), None
        except Exception as e:
            return symbol, None, e

    # Scan paralel menggunakan thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=SCAN_MAX_WORKERS) as executor:
        futures = {executor.submit(_process_symbol, sym): sym for sym in universe}

        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            sym = futures[future]
            try:
                symbol, result, exc = future.result()
                if exc:
                    logger.error(f"  [{i}/{total}] [{symbol}] exception: {exc}")
                    errors.append(symbol)
                elif result.error:
                    logger.warning(f"  [{i}/{total}] [{symbol}] skip: {result.error}")
                    errors.append(symbol)
                else:
                    logger.info(f"  [{i}/{total}] [{symbol}] OK")
                    results.append(result)
                    if result.score_result:
                        update_state(state, symbol,
                                     result.score_result.status,
                                     result.score_result.total_score)
            except Exception as e:
                logger.error(f"  [{i}/{total}] [{sym}] future exception: {e}")
                errors.append(sym)

    cleanup_old_symbols(state, universe)
    save_state(state)

    if errors:
        logger.warning(f"  {len(errors)} gagal: {', '.join(errors)}")
    logger.info(f"  Scan selesai: {len(results)}/{total} berhasil")
    return results, state


# ── Sesi Pagi 08:00 ──────────────────────────────────────────

def run_morning_scan():
    now = _now_wib().strftime("%H:%M WIB")
    logger.info(f"[{now}] SESI PAGI — Morning brief + signal check")

    try:
        # Fetch macro context
        from core.data_fetcher import (
            fetch_morning_briefing,
            fetch_forex_idr_impact,
            fetch_commodities_impact,
        )
        macro = {
            "briefing":    fetch_morning_briefing(),
            "forex":       fetch_forex_idr_impact(),
            "commodities": fetch_commodities_impact(),
        }

        # ── Engine 2-7 (non-teknikal) ──
        try:
            engine_results = run_all_engines()
            logger.info("  Engines selesai")
        except Exception as e:
            logger.warning(f"  Engines error (non-fatal): {e}")
            engine_results = None

        # ── Scan teknikal ──
        results, state = _scan_all(session="morning")
        if not results:
            send_error("Sesi pagi: semua saham gagal di-scan")
            return

        signals = filter_signals(results)

        # ── Kirim alert ──
        send_morning_brief(signals, macro=macro, engine_results=engine_results)

        if engine_results:
            try:
                send_engine_alerts(engine_results)
            except Exception as e:
                logger.warning(f"  Engine alerts error (non-fatal): {e}")

        if engine_results and engine_results.get("events"):
            try:
                from notifications.calendar_alerts import send_new_calendar_alerts
                ncal = send_new_calendar_alerts(engine_results["events"])
                if ncal:
                    logger.info(f"  Kalender korporasi baru: {ncal} entri dikirim")
            except Exception as e:
                logger.warning(f"  Calendar digest error (non-fatal): {e}")

        total_tech = sum(len(v) for v in signals.values())
        logger.info(
            f"  Sinyal teknikal: {total_tech} "
            f"(SB={len(signals['strong_buy'])} "
            f"ACC={len(signals['accumulation'])} "
            f"DIV={len(signals['bull_div'])} "
            f"EE={len(signals['early_entry'])} "
            f"FA={len(signals['frequency_analyzer'])})"
        )

    except Exception as e:
        logger.error(f"Morning scan error: {e}", exc_info=True)
        send_error(f"Sesi pagi error: {e}")

    logger.info("Sesi pagi selesai")


# ── Sesi Tengah Hari 12:00 ─────────────────────────────────────

def run_noon_scan():
    now = _now_wib().strftime("%H:%M WIB")
    logger.info(f"[{now}] SESI 2 — Intraday valid signal check")

    try:
        # ── Engine fresh-from-the-oven (opsional) ──
        if NOON_INCLUDE_ENGINE_FRESH_ALERTS:
            engine_results = None
            try:
                engine_results = run_all_engines()
            except Exception as e:
                logger.warning(f"  Engines error (non-fatal): {e}")
                engine_results = None

            if engine_results:
                try:
                    if NOON_TEST_MODE_IGNORE_HISTORY:
                        # Testing mode: tampilkan apa adanya tanpa dedup/history.
                        send_engine_alerts(engine_results)
                    else:
                        from notifications.engine_fresh import filter_fresh_engine_results
                        fresh_eng = filter_fresh_engine_results(engine_results)
                        send_engine_alerts(fresh_eng)
                except Exception as e:
                    logger.warning(f"  Fresh engine alerts error (non-fatal): {e}")

        results, state = _scan_all(session="noon")
        if not results:
            send_error("Sesi 12:00: semua saham gagal di-scan")
            return

        raw_signals = filter_signals(results)
        noon_signals = filter_intraday_session2_signals(raw_signals)
        send_noon_intraday_alert(noon_signals)

        total_raw = sum(len(v) for v in raw_signals.values())
        total_kept = sum(len(v) for v in noon_signals.values())
        logger.info(
            "  Sinyal sesi-2: %d kandidat terpilih dari %d sinyal awal", total_kept, total_raw
        )
    except Exception as e:
        logger.error("Noon scan error: %s" % e, exc_info=True)
        send_error("Sesi 12:00 error: %s" % e)

    logger.info("Sesi 12:00 selesai")


# ── Sesi Malam 16:00 ─────────────────────────────────────────

def run_evening_scan():
    now = _now_wib().strftime("%H:%M WIB")
    logger.info(f"[{now}] SESI MALAM — Full scan + signal filter")

    try:
        # ── Engine 2-7: market sweep, bandar, insider, sektor, kalender, whale (sama seperti pagi) ──
        engine_results = None
        try:
            engine_results = run_all_engines()
            logger.info("  Engines selesai")
        except Exception as e:
            logger.warning(f"  Engines error (non-fatal): {e}")

        # ── Scan teknikal (seluruh universe dari API) ──
        results, state = _scan_all(session="evening")
        if not results:
            send_error("Sesi malam: semua saham gagal di-scan")
            return

        signals = filter_signals(results)


        # ── Kirim alert teknikal ──
        send_evening_report(signals, engine_results=engine_results)

        # ── Sweep / bandar / insider pasar / sektor / whale (dari API market-level) ──
        if engine_results:
            try:
                send_engine_alerts(engine_results)
            except Exception as e:
                logger.warning("  Engine alerts error (non-fatal): %s" % e)

        # ── Kalender dividen, rights, split, RUPS (entri baru vs cache) ──
        if engine_results and engine_results.get("events"):
            try:
                from notifications.calendar_alerts import send_new_calendar_alerts

                ncal = send_new_calendar_alerts(engine_results["events"])
                if ncal:
                    logger.info("  Kalender korporasi baru: %d entri dikirim" % ncal)
            except Exception as e:
                logger.warning("  Calendar digest error (non-fatal): %s" % e)

        total_tech = sum(len(v) for v in signals.values())
        logger.info(
            "  Sinyal teknikal: %d (SB=%d ACC=%d DIV=%d EE=%d FA=%d)" % (
                total_tech,
                len(signals['strong_buy']),
                len(signals['accumulation']),
                len(signals['bull_div']),
                len(signals['early_entry']),
                len(signals['frequency_analyzer']),
            )
        )

    except Exception as e:
        logger.error("Evening scan error: %s" % e, exc_info=True)
        send_error("Sesi malam error: %s" % e)

    logger.info("Sesi malam selesai")


# ── Entry point ───────────────────────────────────────────────

def start_scheduler():
    logger.info("Scheduler: %s", "OTOMATIS" if AUTO_SCHEDULE else "MANUAL")
    try:
        u = resolve_scan_universe()
        logger.info("Universe : %d saham (all-stocks API atau fallback)" % len(u))
    except Exception:
        logger.info("Universe : (resolve saat scan)")

    send_startup_message()

    if not AUTO_SCHEDULE:
        logger.info("AUTO_SCHEDULE=False -- standby. Jalankan manual via run_*.py")
        while True:
            import time
            time.sleep(60)

    import schedule as sch
    import time

    morning_time = "%02d:%02d" % (MORNING_SCAN_HOUR, MORNING_SCAN_MINUTE)
    noon_time = "%02d:%02d" % (NOON_SCAN_HOUR, NOON_SCAN_MINUTE)
    evening_time = "%02d:%02d" % (EVENING_SCAN_HOUR, EVENING_SCAN_MINUTE)

    sch.every().day.at(morning_time).do(run_morning_scan)
    sch.every().day.at(noon_time).do(run_noon_scan)
    sch.every().day.at(evening_time).do(run_evening_scan)

    logger.info(
        "Jadwal aktif: pagi=%s, sesi2=%s, malam=%s WIB"
        % (morning_time, noon_time, evening_time)
    )

    while True:
        sch.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    start_scheduler()
