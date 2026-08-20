"""
Script refresh snapshot profil perusahaan (IDX + Yahoo Finance)
untuk seluruh SAHAM_LIST. Dijalankan otomatis via GitHub Actions
(.github/workflows/update_company_profiles_cache.yml) karena
Streamlit Cloud sering diblokir/rate-limited oleh IDX & Yahoo.

Jalankan manual kalau perlu:

    python update_company_profiles_cache.py [--limit 20]

Setelah selesai, commit dan push data/company_profiles_cache.parquet.
"""
import sys
import os
import time
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.config.saham_list import SAHAM_LIST
from app.stock_analysis.idx_fetch import fetch_idx_raw, fetch_yf_raw
from app.stock_analysis import profile_cache

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=None, help="Batasi jumlah emiten (untuk testing)")
parser.add_argument("--delay", type=float, default=0.5, help="Jeda antar emiten (detik)")
args = parser.parse_args()

kode_list = SAHAM_LIST[: args.limit] if args.limit else SAHAM_LIST
total = len(kode_list)

df = profile_cache.load_cache()

ok_idx = ok_yf = fail_idx = fail_yf = 0
now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")

for i, kode in enumerate(kode_list, start=1):

    row = {"updated_at": now_iso}

    try:
        idx_data = fetch_idx_raw(kode)
        row.update(profile_cache.row_from_idx(idx_data))
        row["idx_error"] = None
        ok_idx += 1
    except Exception as e:
        row["idx_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        fail_idx += 1

    try:
        yf_data = fetch_yf_raw(kode)
        row.update(profile_cache.row_from_yf(yf_data))
        row["yf_error"] = None
        ok_yf += 1
    except Exception as e:
        row["yf_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        fail_yf += 1

    # Kalau DUA-duanya gagal, jangan timpa baris lama (kalau ada) —
    # biarkan data snapshot sebelumnya tetap dipakai app, daripada
    # dihapus jadi kosong gara-gara kegagalan sementara.
    both_failed = row.get("nama") is None and row.get("yf_summary") is None
    existing = df[df["kode"] == kode] if "kode" in df.columns else None
    has_existing = existing is not None and not existing.empty

    if both_failed and has_existing:
        print(f"[{i}/{total}] {kode}: GAGAL total, pertahankan data lama")
    else:
        df = profile_cache.upsert_row(df, kode, row)
        print(
            f"[{i}/{total}] {kode}: "
            f"IDX={'OK' if row['idx_error'] is None else 'FAIL'} "
            f"YF={'OK' if row['yf_error'] is None else 'FAIL'}"
        )

    # Simpan progres tiap 50 emiten supaya kalau job terhenti
    # di tengah jalan, hasil sejauh ini tidak hilang.
    if i % 50 == 0:
        profile_cache.save_cache(df)

    time.sleep(args.delay)

profile_cache.save_cache(df)

print("\n" + "=" * 60)
print(f"Selesai: {total} emiten diproses")
print(f"IDX  sukses: {ok_idx} | gagal: {fail_idx}")
print(f"Yahoo sukses: {ok_yf} | gagal: {fail_yf}")
print(f"Snapshot tersimpan di: {profile_cache.CACHE_PATH}")
print(f"Total baris di cache: {len(df)}")

if ok_idx == 0 and ok_yf == 0:
    print("\nGAGAL TOTAL: tidak ada satupun emiten berhasil diambil.")
    sys.exit(1)
