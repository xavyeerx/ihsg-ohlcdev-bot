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

# Universe scan utama (watchlist kustom). Dipakai oleh resolve_scan_universe().
CUSTOM_SCAN_UNIVERSE = [
    "RAJA", "RATU", "MINA", "BUVA", "PADI", "BNBR", "VKTR", "BRMS", "BUMI", "DEWA",
    "ENRG", "PTRO", "BRPT", "CUAN", "CDIA", "TPIA", "BREN", "DSSA", "IMPC", "BIPI",
    "COIN", "SUPA", "MBMA", "ESSA", "ADMR", "EMAS", "AADI", "ADRO", "ANTM", "NCKL",
    "INCO", "INDY", "HRUM", "NICL", "ARCI", "HRTA", "MBSS", "BULL", "OASA", "KETR",
    "SOCI", "DOOH", "INET", "CBRE", "WIFI", "HUMI", "FORE", "BELL", "ZATA", "ASHA",
    "RMKE", "RMKO", "GZCO", "COCO", "DATA", "MDIA", "PSKT", "CBDK", "BKSL", "PANI",
    "TRUE", "TRIN", "WIIM", "TINS", "PPRE", "APLN", "PYFA", "ASSA", "BUKA", "SCMA",
    "PTBA",
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

# Fallback bila mode API gagal (jarang dipakai jika SCAN_UNIVERSE_MODE=custom).
SCAN_UNIVERSE_FALLBACK = list(CUSTOM_SCAN_UNIVERSE)


def resolve_scan_universe():
    """
    Universe scan.
    Mode default: CUSTOM_SCAN_UNIVERSE (watchlist statis).
    Set env SCAN_UNIVERSE_MODE=api untuk semua saham dari API /api/main/symbols.
    Set SCAN_UNIVERSE_MODE=kompas100 untuk fallback KOMPAS100.
    """
    import os

    mode = os.getenv("SCAN_UNIVERSE_MODE", "custom").strip().lower()

    if mode == "custom":
        syms = list(CUSTOM_SCAN_UNIVERSE)
        logger.info("resolve_scan_universe: custom watchlist (%d simbol).", len(syms))
        return syms

    if mode == "kompas100":
        logger.info(
            "resolve_scan_universe: KOMPAS100 (%d simbol).",
            len(KOMPAS100),
        )
        return list(KOMPAS100)

    if mode == "api":
        try:
            from core.data_fetcher import fetch_all_symbols

            syms = fetch_all_symbols()
            if syms:
                logger.info("resolve_scan_universe: API all-stocks (%d simbol).", len(syms))
                return syms
        except Exception as e:
            logger.warning("resolve_scan_universe: API error %s — pakai custom.", e)

    syms = list(SCAN_UNIVERSE_FALLBACK)
    logger.info("resolve_scan_universe: fallback custom (%d simbol).", len(syms))
    return syms


# Kompatibilitas: kode lama yang import SCAN_UNIVERSE.
SCAN_UNIVERSE = list(CUSTOM_SCAN_UNIVERSE)
