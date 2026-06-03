"""
Script update cache minyak goreng dari SISKAPERBAPO.
Jalankan dari lokal Indonesia (bukan Streamlit Cloud):

    python update_mg_cache.py [--days 30]

Setelah selesai, commit dan push file data/minyakgoreng_cache.parquet ke git.
Streamlit Cloud akan otomatis pakai file cache tersebut.
"""
import sys
import os
import argparse

# Pastikan root project masuk Python path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.utils.cpo_engine import (
    get_minyakgoreng_all_history,
    _load_mg_cache,
    _MG_CACHE_PATH,
)

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, default=30, help="Jumlah hari ke belakang (default: 30)")
args = parser.parse_args()

print(f"Mengambil data {args.days} hari terakhir dari SISKAPERBAPO...")
df = get_minyakgoreng_all_history(days=args.days)

if df.empty:
    print("GAGAL: Tidak ada data yang berhasil diambil. Periksa koneksi internet.")
    sys.exit(1)

print(f"Berhasil: {len(df)} baris data")
print(df.groupby("Jenis")[["Harga"]].agg(["min", "max", "count"]).to_string())

cache = _load_mg_cache()
print(f"\nCache tersimpan di: {_MG_CACHE_PATH}")
print(f"Total baris di cache: {len(cache)}")
