# ============================================================
# KONFIGURASI UTAMA - IHSG IDX Intelligence Bot
# ============================================================
import os

# --- [WAJIB DIISI] Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8771268923:AAGkIHtDhwi-3DqFBmHCc_wNiZ4K4UvmVYM")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "-1003910083132")

# --- RapidAPI ---
RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "1e135405dcmsh286e1cc50e2dd2bp13cc0fjsn2a349277ca95")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "indonesia-stock-exchange-idx.p.rapidapi.com")

# --- Runtime mode ---
# True: main.py hanya standby command Telegram, tidak resolve universe/scan otomatis.
# Cocok untuk VM hemat API; RapidAPI baru dipanggil ketika user menjalankan command.
COMMAND_ONLY_MODE = os.getenv("COMMAND_ONLY_MODE", "true").lower() in ("1", "true", "yes", "on")

# --- Scanning ---
SCAN_INTERVAL_MINUTES = 60
MARKET_OPEN_HOUR      = 9
MARKET_OPEN_MINUTE    = 0
MARKET_CLOSE_HOUR     = 15
MARKET_CLOSE_MINUTE   = 30
TIMEZONE              = "Asia/Jakarta"

# --- Jadwal dual-session ---
MORNING_SCAN_HOUR   = 8
MORNING_SCAN_MINUTE = 0
NOON_SCAN_HOUR      = 12
NOON_SCAN_MINUTE    = 0
EVENING_SCAN_HOUR   = 18
EVENING_SCAN_MINUTE = 30

# Kirim Telegram morning brief (makro). False = tidak fetch & tidak kirim (hemat quota).
MORNING_BRIEF_ALERT_ENABLED = False

# --- Output config ---
TOP_N_STRONG_BUY   = 3
TOP_N_ACCUMULATION = 3

# --- Supertrend ---
SUPERTREND_PERIOD     = 10
SUPERTREND_MULTIPLIER = 3.0

# --- EMA ---
EMA_FAST   = 20
EMA_MEDIUM = 50
EMA_SLOW   = 200

# --- RSI ---
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70

# --- Stochastic RSI ---
STOCH_PERIOD     = 14
SMOOTH_K         = 3
SMOOTH_D         = 3
STOCH_OVERSOLD   = 20
STOCH_OVERBOUGHT = 80

# --- ATR ---
ATR_PERIOD      = 14
MIN_ATR_PERCENT = 0.5

# --- ADX ---
ADX_PERIOD    = 14
ADX_THRESHOLD = 25

# --- MACD ---
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

# --- Volume (sama dengan bot lama ihsg-supertrend-scanner v5) ---
VOLUME_PERIOD            = 20
VOLUME_SPIKE_THRESHOLD   = 1.5
UNUSUAL_VOLUME_THRESHOLD = 2.5
MIN_VOLUME               = 100_000

# --- Frequency Analyzer ---
# Deteksi lonjakan frekuensi transaksi (mirip indikator "Frequency Analyzer").
FREQUENCY_PERIOD          = 20
FREQUENCY_SPIKE_THRESHOLD = 2.0
FREQUENCY_SURGE_THRESHOLD = 3.0
FREQ_ANALYZER_SPIKE_THRESHOLD = 2.3
FREQ_ANALYZER_SURGE_THRESHOLD = 3.2
# Syarat akhir is_frequency_analyzer (naikkan jika masih terlalu ramai).
FA_MIN_STRENGTH    = 6   # lebih ketat: spike harus didukung konfirmasi kuat
FA_MIN_FLOW_SCORE  = 68  # lebih ketat: kurangi kandidat "setengah jadi"
FA_MAX_VOLUME_RATIO = 0.5  # volume_ratio wajib di bawah ini (stealth / vol kecil)

# --- Momentum ---
MOMENTUM_PERIOD = 10

# --- Pivot / Support-Resistance (sama dengan bot lama) ---
PIVOT_LOOKBACK = 10

# --- Divergence ---
DIV_PIVOT_LOOKBACK       = 5
DIV_MIN_SEPARATION       = 5
DIV_MAX_SEPARATION       = 50
DIV_PRICE_MIN_DROP       = 0.5
DIV_RSI_MIN_DIFF         = 2.0
DIV_RSI_OVERSOLD         = 50.0
DIV_FRESHNESS_BARS       = 5
DIV_STOCH_MAX_K          = 80.0
DIV_VOLUME_DECLINE_RATIO = 0.85

# --- DCA Zones ---
DCA_LOOKBACK         = 50
FIB_LEVEL_1          = 61.8
FIB_LEVEL_2          = 85.0
DCA_VOLUME_THRESHOLD = 0.7

# --- Target Profit ---
TP1_MULTIPLIER     = 1.0
TP2_MULTIPLIER     = 2.5
TP2_MIN_MULTIPLIER = 1.3
TP2_MAX_MULTIPLIER = 3.0

# --- Scoring Thresholds ---
# Total max = 100 | Teknikal: 70 pts | Bandarmology: 30 pts
# Disesuaikan dengan bot lama: BUY_THRESHOLD=70, ACCUMULATE=55, HOLD=40
STRONG_BUY_THRESHOLD = 70
ACCUMULATE_THRESHOLD = 55
HOLD_THRESHOLD       = 40

# --- Bandarmology Config ---
BROKSUM_NET_BUY_DAYS = 3
FREQ_LOW_THRESHOLD   = 0.7
FOREIGN_FLOW_DAYS    = 5

# --- Broker Trade Chart (opsional; hemat quota jika False) ---
BROKER_CHART_ENABLED = False

# --- Data Fetching ---
OHLCV_INTERVAL   = "daily"
OHLCV_BARS       = 90
# Sesi 12:00 — teknikal intraday (API: 1m,5m,15m,30m,1h,2h,3h,4h)
NOON_OHLCV_INTERVAL = "4h"
NOON_OHLCV_BARS     = 120
NOON_DAILY_BARS     = 120   # untuk likuiditas + bias harian + bandarmology (asing/freq)
# Sertakan run_all_engines + send_engine_alerts setelah scan sesi 12 (sweep, bandar, insider, sektor, whale).
# Default False: hemat quota & hindari duplikasi dengan malam. Set True jika ingin engine juga di siang.
# OHLC intraday = candle dari API (4h/daily terbaru saat fetch), bukan WebSocket tick-by-tick.
NOON_INCLUDE_ENGINE_FRESH_ALERTS = False
# Mode testing sesi 12:
# True  -> abaikan cache/history fresh, tampilkan data apa adanya setiap run.
# False -> hanya kirim item engine yang benar-benar baru (fresh-only).
NOON_TEST_MODE_IGNORE_HISTORY = True
REQUEST_TIMEOUT  = 20   # naik 15→20 detik, kurangi timeout spurious
MAX_RETRIES      = 2    # turun 3→2, gagal cepat daripada retry lama
RATE_LIMIT_DELAY = 0.0  # Ultra: tidak perlu delay antar retry

# --- Concurrency ---
# Scan ~800+ simbol: naikkan jika API kuat; turunkan jika 429/timeout.
SCAN_MAX_WORKERS = 72

# --- Signal Detection ---
CONFIRMATION_BARS    = 2               # bar konfirmasi breakout supertrend
MIN_DAILY_TURNOVER   = 5_000_000_000   # 5 Miliar IDR — filter likuiditas

# --- Intraday Session-2 (12:00) ---
# Filter agar alert jam 12 fokus kandidat yang masih fresh untuk lanjut sesi 2.
INTRADAY_NOON_MIN_SCORE      = 45
INTRADAY_NOON_MIN_UPSIDE_PCT = 0.2
INTRADAY_NOON_MAX_RUNUP_PCT  = 15.0
# Selaraskan dengan screening malam (daily): hanya jika struktur daily masih mendukung.
INTRADAY_NOON_REQUIRE_DAILY_BIAS = False
INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA50 = False
INTRADAY_NOON_DAILY_CLOSE_ABOVE_EMA20 = True

# --- Non-Retail Flow Alert ---
# Filter saham masuk daftar akumulasi non-retail:
#   1. nr_net / grand_total >= NON_RETAIL_FLOW_MIN_PCT  (net asing+pemerintah signifikan)
#   2. buyer_count < seller_count                       (beli terkonsentrasi = akumulasi)
# Diurutkan dari NR net% terbesar. Alert hanya di sesi malam dan siang.
NON_RETAIL_FLOW_MIN_PCT = 20.0   # % minimum net non-retail dari grand total

# Non-retail flow akumulasi 5 hari trading (broksum harian, ~1 minggu)
NON_RETAIL_FLOW_5D_ALERT_ENABLED = True
NON_RETAIL_FLOW_5D_TRADING_DAYS = 5
NON_RETAIL_FLOW_5D_MIN_PCT = 20.0   # sum(nr_net 5h) / sum(grand_total 5h) >= ini
NON_RETAIL_FLOW_5D_MAX_CALENDAR_LOOKBACK = 21

# --- Insider Alert Filter ---
# Hanya kirim insider transaksi besar + net buy akumulasi dalam window hari ini.
INSIDER_ALERT_WINDOW_DAYS = 7
INSIDER_ALERT_MIN_VALUE   = 5_000_000_000  # 5B IDR

