# ============================================================
# STATE MANAGER — Menyimpan status saham antar scan
# ============================================================
# Digunakan untuk mendeteksi perubahan status (e.g., HOLD → ACCUMULATE)
# sehingga alert hanya dikirim saat ada perubahan signifikan.

import json, os, logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# File state disimpan di folder yang sama dengan modul ini
STATE_FILE = os.path.join(os.path.dirname(__file__), "scan_state.json")


def load_state() -> Dict:
    """
    Memuat state sebelumnya dari file JSON.
    Mengembalikan dict kosong jika file tidak ada atau corrupt.
    """
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Gagal membaca state file: {e} — reset state")
        return {}


def save_state(state: Dict) -> bool:
    """
    Menyimpan state ke file JSON.
    Returns True jika berhasil.
    """
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Gagal menyimpan state: {e}")
        return False


def get_prev_status(state: Dict, symbol: str) -> str:
    """Mengambil status sebelumnya untuk satu saham."""
    return state.get(symbol, {}).get("status", "")


def update_state(state: Dict, symbol: str, status: str, score: float) -> Dict:
    """
    Update state untuk satu saham setelah scan.
    Menyimpan: status, score, dan timestamp terakhir update.
    Mempertahankan nr_history (akumulasi broksum harian).
    """
    prev = state.get(symbol, {}) if isinstance(state.get(symbol), dict) else {}
    state[symbol] = {
        "status":     status,
        "score":      score,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "nr_history": prev.get("nr_history", []),
    }
    return state


def build_prev_states(state: Dict) -> Dict[str, str]:
    """
    Konversi state dict menjadi {symbol: status} untuk dipakai scanner.
    Scanner butuh mapping sederhana symbol → status lama.
    """
    return {sym: data.get("status", "") for sym, data in state.items()}


def cleanup_old_symbols(state: Dict, active_symbols: list) -> Dict:
    """
    Hapus simbol yang sudah tidak di-scan dari state
    agar file tidak membengkak.
    """
    active_set = set(active_symbols)
    removed = [s for s in list(state.keys()) if s not in active_set]
    for s in removed:
        del state[s]
    if removed:
        logger.info(f"Cleanup state: hapus {len(removed)} simbol lama")
    return state
