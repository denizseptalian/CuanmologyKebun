# ==========================================================
# 📦 SNAPSHOT CACHE — COMPANY PROFILES
# ==========================================================
# Data profil + pemegang saham (IDX) dan deskripsi (Yahoo) untuk
# SEMUA emiten di-refresh harian oleh GitHub Actions
# (update_company_profiles_cache.py) dan disimpan sebagai parquet
# yang di-commit ke repo. App membaca dari sini dulu sebelum
# mencoba live-fetch — Streamlit Cloud sering diblokir/dibatasi
# oleh IDX & Yahoo, sedangkan GitHub Actions punya IP berbeda.
# ==========================================================

import json
import os

import pandas as pd

CACHE_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..",
        "data", "company_profiles_cache.parquet",
    )
)

COLUMNS = [
    "kode",
    "nama", "kegiatan_usaha", "sektor", "industri", "sub_industri",
    "alamat", "website", "papan", "tanggal_ipo",
    "pemegang_saham_json", "direktur_json", "komisaris_json",
    "yf_summary", "yf_market_cap", "yf_employees",
    "yf_insider_pct", "yf_institution_pct", "yf_officers_json",
    "idx_error", "yf_error",
    "updated_at",
]


# ==========================================================
# LOAD / SAVE (dipakai oleh script batch)
# ==========================================================

def load_cache() -> pd.DataFrame:
    if not os.path.exists(CACHE_PATH):
        return pd.DataFrame(columns=COLUMNS)
    try:
        return pd.read_parquet(CACHE_PATH)
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def save_cache(df: pd.DataFrame):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    df = df.drop_duplicates(subset=["kode"], keep="last").reset_index(drop=True)
    df.to_parquet(CACHE_PATH, index=False)


def upsert_row(df: pd.DataFrame, kode: str, row: dict) -> pd.DataFrame:
    """Ganti baris untuk `kode` (tambah kalau belum ada)."""
    row = {**{c: None for c in COLUMNS}, **row, "kode": kode}
    df = df[df["kode"] != kode]
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def row_from_idx(idx_data: dict) -> dict:
    return {
        "nama": idx_data.get("nama"),
        "kegiatan_usaha": idx_data.get("kegiatan_usaha"),
        "sektor": idx_data.get("sektor"),
        "industri": idx_data.get("industri"),
        "sub_industri": idx_data.get("sub_industri"),
        "alamat": idx_data.get("alamat"),
        "website": idx_data.get("website"),
        "papan": idx_data.get("papan"),
        "tanggal_ipo": idx_data.get("tanggal_ipo"),
        "pemegang_saham_json": json.dumps(idx_data.get("pemegang_saham") or []),
        "direktur_json": json.dumps(idx_data.get("direktur") or []),
        "komisaris_json": json.dumps(idx_data.get("komisaris") or []),
    }


def row_from_yf(yf_data: dict) -> dict:
    return {
        "yf_summary": yf_data.get("summary"),
        "yf_market_cap": yf_data.get("market_cap"),
        "yf_employees": yf_data.get("employees"),
        "yf_insider_pct": yf_data.get("insider_pct"),
        "yf_institution_pct": yf_data.get("institution_pct"),
        "yf_officers_json": json.dumps(yf_data.get("officers") or []),
    }


# ==========================================================
# READ (dipakai oleh app — cepat, tanpa network)
# ==========================================================

def _to_idx_shape(row: pd.Series):
    if pd.isna(row.get("nama")):
        return None

    def _j(col):
        try:
            raw = row.get(col)
            return json.loads(raw) if raw else []
        except Exception:
            return []

    return {
        "nama": row.get("nama"),
        "kegiatan_usaha": row.get("kegiatan_usaha"),
        "sektor": row.get("sektor"),
        "industri": row.get("industri"),
        "sub_industri": row.get("sub_industri"),
        "alamat": row.get("alamat"),
        "website": row.get("website"),
        "papan": row.get("papan"),
        "tanggal_ipo": row.get("tanggal_ipo"),
        "pemegang_saham": _j("pemegang_saham_json"),
        "direktur": _j("direktur_json"),
        "komisaris": _j("komisaris_json"),
    }


def _to_yf_shape(row: pd.Series):
    if pd.isna(row.get("yf_summary")) and pd.isna(row.get("yf_market_cap")):
        return None

    try:
        officers = json.loads(row.get("yf_officers_json") or "[]")
    except Exception:
        officers = []

    return {
        "summary": row.get("yf_summary"),
        "market_cap": row.get("yf_market_cap"),
        "employees": row.get("yf_employees"),
        "insider_pct": row.get("yf_insider_pct"),
        "institution_pct": row.get("yf_institution_pct"),
        "officers": officers,
    }


def read_snapshot(kode: str):
    """Return (idx_dict_or_None, yf_dict_or_None, updated_at_str_or_None).

    Semua None kalau kode belum ada di snapshot sama sekali
    (misal emiten baru IPO, belum sempat ke-refresh).
    """
    df = load_cache()

    if df.empty or "kode" not in df.columns:
        return None, None, None

    match = df[df["kode"] == kode]
    if match.empty:
        return None, None, None

    row = match.iloc[-1]

    return (
        _to_idx_shape(row),
        _to_yf_shape(row),
        row.get("updated_at"),
    )
