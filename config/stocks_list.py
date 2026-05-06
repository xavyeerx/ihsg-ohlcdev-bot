# ============================================================
# DAFTAR SAHAM IHSG
# ============================================================

# IDX30 -- konstituen resmi per April 2026
# Sumber: idx.co.id/produk/indeks/idx30
IDX30 = [
    "ADMR", "AMMN", "ANTM", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BMRI", "BRIS",
    "BRPT", "BUKA", "CUAN", "ESSA", "EXCL",
    "GOTO", "ICBP", "INCO", "INDF", "ISAT",
    "ITMG", "MDKA", "MEDC", "MTEL", "PGAS",
    "PTBA", "SMGR", "TLKM", "TOWR", "UNVR",
    "PTMP"
]

# Indeks KOMPAS100 — komposisi disinkronkan dari lampiran BEI / sumber indeks.
# Update berkala (~6 bulan): sesuaikan daftar setelah pengumuman rebalancing resmi.
# Sumber referensi: idxstock.com (evaluasi mayor Jan 2025); irisan dengan API aktif.
KOMPAS100 = [
    "ACES", "ADMR", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ARTO", "ASII", "AUTO",
    "AVIA", "BBCA", "BBNI", "BBRI", "BBTN", "BBYB", "BDKR", "BFIN", "BMRI", "BMTR",
    "BNGA", "BRIS", "BRMS", "BRPT", "BSDE", "BTPS", "CMRY", "CPIN", "CTRA", "DEWA",
    "DSNG", "ELSA", "EMTK", "ENRG", "ERAA", "ESSA", "EXCL", "FILM", "GGRM", "GJTL",
    "GOTO", "HEAL", "HMSP", "HRUM", "ICBP", "INCO", "INDF", "INDY", "INET", "INKP",
    "INTP", "ISAT", "ITMG", "JPFA", "JSMR", "KIJA", "KLBF", "KPIG", "LSIP", "MAPA",
    "MAPI", "MARK", "MBMA", "MDKA", "MEDC", "MIDI", "MIKA", "MNCN", "MTEL", "MYOR",
    "NCKL", "NISP", "PANI", "PGAS", "PGEO", "PNLF", "PTBA", "PTPP", "PTRO", "PWON",
    "RAJA", "SCMA", "SIDO", "SMGR", "SMIL", "SMRA", "SRTG", "SSIA", "SSMS", "SURI",
    "TINS", "TKIM", "TLKM", "TOBA", "TOWR", "TPIA", "UNIQ", "UNTR", "UNVR", "WIFI",
]

# LQ45 tambahan (di luar IDX30) untuk ekspansi nanti
PRIORITY_STOCKS = [
    "BBCA", "BBRI", "BMRI", "TLKM", "ASII",
    "UNVR", "ICBP", "INDF", "KLBF", "GGRM",
    "HMSP", "BBNI", "BRIS", "BRPT", "INCO",
    "ANTM", "PTBA", "ADRO", "ITMG", "PGAS",
    "SMGR", "INTP", "JSMR", "WIKA", "WSKT",
    "EXCL", "ISAT", "MTEL", "TOWR", "TBIG",
    "GOTO", "BUKA", "EMTK", "FILM", "MAPI",
    "CPIN", "JPFA", "MAIN", "SIDO", "MYOR",
    "ACES", "LSIP", "AALI", "SSMS", "DSNG",
]

MIDCAP_STOCKS = [
    "BNGA", "NISP", "BDMN", "BJBR", "BJTM",
    "HEAL", "MIKA", "SILO", "PRDA", "ESSA",
    "MDKA", "AMMN", "DSSA", "MBMA", "NCKL",
    "SMDR", "TPMA", "ASSA", "BIRD", "TAXI",
    "AKRA", "RAJA", "TPIA", "DPNS", "CTRA",
    "BSDE", "SMRA", "PWON", "LPKR", "DMAS",
]

ALL_STOCKS  = PRIORITY_STOCKS + MIDCAP_STOCKS
TEST_STOCKS = ["BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "GOTO"]

import logging

logger = logging.getLogger(__name__)

# Daftar statis (fallback bila API /main/symbols gagal). Scan runtime pakai resolve_scan_universe().
SCAN_UNIVERSE_FALLBACK = list(KOMPAS100)


def resolve_scan_universe():
    """
    Universe scan: semua saham aktif IHSG dari API /api/main/symbols.
    Fallback ke KOMPAS100 jika API kosong / error.
    """
    try:
        from core.data_fetcher import fetch_all_symbols

        syms = fetch_all_symbols()
        if syms:
            logger.info("resolve_scan_universe: API all-stocks (%d simbol).", len(syms))
            return syms
    except Exception as e:
        logger.warning("resolve_scan_universe: %s — pakai fallback.", e)
    logger.info(
        "resolve_scan_universe: fallback KOMPAS100 (%d simbol).",
        len(SCAN_UNIVERSE_FALLBACK),
    )
    return list(SCAN_UNIVERSE_FALLBACK)


# Kompatibilitas: kode lama yang import SCAN_UNIVERSE tetap dapat daftar fallback.
SCAN_UNIVERSE = SCAN_UNIVERSE_FALLBACK
