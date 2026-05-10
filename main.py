#!/usr/bin/env python3
# ============================================================
# MAIN — Entry point IHSG IDX Intelligence Bot v2
# ============================================================
# Cara menjalankan:
#   cd ihsg-ohlcdev-bot
#   python main.py
#
# Bot akan:
#   1. Kirim pesan startup ke Telegram
#   2. Sesi pagi 08:00 WIB  : macro brief + signal scan + engine alerts
#   3. Sesi malam (lihat EVENING_* di settings) : full signal scan
# Scan/alert terjadwal hanya Senin–Jumat WIB (IDX libur Sabtu–Minggu).
#
# Screening: Strong Buy, Accumulation, Bull Div, Early Entry, Freq Analyzer;
#   insider + kalender (dividen, RUPS, RI, SS). Universe: all stocks (API).
# ============================================================

import logging, sys, os

# Pastikan root project ada di sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# -- Logging setup --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "bot.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)

# -- Import modul utama --
from config.settings import (
    OHLCV_INTERVAL, TIMEZONE,
    MORNING_SCAN_HOUR, MORNING_SCAN_MINUTE,
    NOON_SCAN_HOUR, NOON_SCAN_MINUTE,
    EVENING_SCAN_HOUR, EVENING_SCAN_MINUTE,
    COMMAND_ONLY_MODE,
)
from config.stocks_list import resolve_scan_universe
from notifications.telegram_bot import send_startup_message, send_error
from scheduler import start_scheduler


def main():
    logger.info("=" * 55)
    logger.info("  IHSG IDX Intelligence Bot v2 -- STARTING")
    logger.info("=" * 55)
    if COMMAND_ONLY_MODE:
        logger.info("  Mode     : COMMAND ONLY (hemat API, standby Telegram command)")
    else:
        try:
            u = resolve_scan_universe()
            logger.info("  Universe : %d saham (API all-stocks atau fallback)", len(u))
        except Exception as e:
            logger.warning("  Universe : resolve gagal (%s), akan dicoba lagi saat scan", e)
    logger.info(f"  OHLCV    : {OHLCV_INTERVAL} | TZ: {TIMEZONE}")
    logger.info(f"  Sesi pagi: {MORNING_SCAN_HOUR:02d}:{MORNING_SCAN_MINUTE:02d} WIB")
    logger.info(f"  Sesi 2   : {NOON_SCAN_HOUR:02d}:{NOON_SCAN_MINUTE:02d} WIB")
    logger.info(f"  Sesi mlm : {EVENING_SCAN_HOUR:02d}:{EVENING_SCAN_MINUTE:02d} WIB")
    logger.info("=" * 55)

    try:
        start_scheduler()
    except KeyboardInterrupt:
        logger.info("Bot dihentikan oleh user (KeyboardInterrupt)")
        send_error("Bot dihentikan secara manual.")
    except Exception as e:
        logger.critical(f"Bot crash: {e}", exc_info=True)
        send_error(f"Bot crash: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
