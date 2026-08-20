# ==========================================================
# PERSISTENT STORAGE - TRADING TRACKER
# ==========================================================
# Backend:
# 1. Google Sheets — dipakai jika st.secrets berisi
#    [gcp_service_account] dan TRACKER_SHEET_ID.
#    Wajib untuk Streamlit Cloud karena filesystem-nya
#    ephemeral (CSV lokal hilang setiap redeploy).
# 2. CSV lokal — fallback untuk development di komputer sendiri.
#
# Saat worksheet di Google Sheets belum ada, isi CSV lama di repo
# dipakai sebagai seed satu kali sehingga data lama ikut termigrasi.
# ==========================================================

import os
import time

import pandas as pd

TRADES_CSV = "data/trades.csv"
DIVIDENDS_CSV = "dividends.csv"

_CSV_PATHS = {
    "trades": TRADES_CSV,
    "dividends": DIVIDENDS_CSV,
}

# Cache in-memory supaya tiap rerun Streamlit tidak selalu
# memanggil API Sheets. Kadaluarsa singkat agar edit manual
# langsung di spreadsheet tetap terbaca.
_CACHE_TTL_SECONDS = 60
_cache = {}

_spreadsheet_client = None


# ==========================================================
# SECRETS / BACKEND SELECTION
# ==========================================================

def _get_secrets():
    try:
        import streamlit as st

        if (
            "gcp_service_account" in st.secrets
            and "TRACKER_SHEET_ID" in st.secrets
        ):
            return st.secrets
    except Exception:
        pass
    return None


def use_gsheets() -> bool:
    return _get_secrets() is not None


# ==========================================================
# GOOGLE SHEETS CLIENT
# ==========================================================

def _spreadsheet():
    global _spreadsheet_client

    if _spreadsheet_client is None:
        import gspread
        from google.oauth2.service_account import Credentials

        secrets = _get_secrets()

        creds = Credentials.from_service_account_info(
            dict(secrets["gcp_service_account"]),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )

        gc = gspread.authorize(creds)

        _spreadsheet_client = gc.open_by_key(
            secrets["TRACKER_SHEET_ID"]
        )

    return _spreadsheet_client


def _worksheet(name: str, columns):
    import gspread

    ss = _spreadsheet()

    try:
        return ss.worksheet(name)

    except gspread.WorksheetNotFound:

        ws = ss.add_worksheet(
            title=name,
            rows=1000,
            cols=max(len(columns), 12),
        )

        # Seed satu kali dari CSV lama di repo (migrasi data lama)
        seed = _load_csv(name, columns)

        if not seed.empty:
            _write_worksheet(ws, seed)
        else:
            ws.update([list(columns)])

        return ws


def _write_worksheet(ws, df: pd.DataFrame):
    df = df.copy().fillna("")

    values = [df.columns.tolist()] + (
        df.astype(str)
        .replace({"nan": "", "NaT": "", "None": ""})
        .values.tolist()
    )

    ws.clear()

    # RAW: nilai disimpan apa adanya (tanggal tetap string ISO,
    # tidak diparse ulang oleh locale spreadsheet)
    ws.update(values, value_input_option="RAW")


# ==========================================================
# CSV FALLBACK
# ==========================================================

def _load_csv(name: str, columns) -> pd.DataFrame:
    path = _CSV_PATHS[name]

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=columns)

    df = pd.read_csv(path)

    if name == "dividends":
        # CSV dividen lama punya kolom header rusak — ambil
        # hanya kolom yang valid
        df = df[[c for c in columns if c in df.columns]]

    return df


# ==========================================================
# PUBLIC API
# ==========================================================

def load_table(name: str, columns) -> pd.DataFrame:

    if not use_gsheets():
        return _load_csv(name, columns)

    cached = _cache.get(name)

    if cached is not None:
        df, ts = cached
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return df.copy()

    ws = _worksheet(name, columns)

    records = ws.get_all_records()

    if records:
        df = pd.DataFrame(records)
    else:
        df = pd.DataFrame(columns=columns)

    _cache[name] = (df.copy(), time.time())

    return df


def save_table(name: str, df: pd.DataFrame):

    df = df.reset_index(drop=True)

    if not use_gsheets():
        path = _CSV_PATHS[name]
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        df.to_csv(path, index=False)
        return

    ws = _worksheet(name, df.columns)

    _write_worksheet(ws, df)

    _cache[name] = (df.copy(), time.time())
