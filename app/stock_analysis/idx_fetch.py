# ==========================================================
# 🌐 RAW FETCHERS — IDX & YAHOO FINANCE COMPANY PROFILE
# ==========================================================
# Modul murni Python (TANPA dependency ke streamlit) supaya bisa
# dipakai baik oleh app (app/stock_analysis/company_profile.py,
# di-cache dengan st.cache_data) maupun oleh script batch yang
# jalan di GitHub Actions (update_company_profiles_cache.py) untuk
# membangun snapshot harian.
#
# Setiap fungsi mengembalikan dict yang sudah dinormalisasi, atau
# raise Exception kalau gagal — pemanggil yang menentukan cara
# menangani kegagalan (retry, fallback, dsb).
# ==========================================================

import time

IDX_PROFILE_URL = (
    "https://www.idx.co.id/primary/ListedCompany/"
    "GetCompanyProfilesDetail?KodeEmiten={kode}&language=id-id"
)


# ==========================================================
# IDX
# ==========================================================

def fetch_idx_raw(kode: str) -> dict:
    """Ambil profil + pemegang saham + pengurus dari API IDX.

    Raise Exception dengan pesan ringkas kalau semua percobaan gagal.
    """
    from curl_cffi import requests as creq

    referer = (
        "https://www.idx.co.id/id/perusahaan-tercatat/"
        f"profil-perusahaan-tercatat/{kode}"
    )

    headers = {
        "Referer": referer,
        "Origin": "https://www.idx.co.id",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "X-Requested-With": "XMLHttpRequest",
    }

    last_err = "unknown"

    for imp in ("chrome", "safari", "edge", "chrome_android"):
        try:
            r = creq.get(
                IDX_PROFILE_URL.format(kode=kode),
                impersonate=imp,
                headers=headers,
                timeout=15,
            )

            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
                continue

            data = r.json()

            if data.get("Profiles"):
                p = data["Profiles"][0]
                return {
                    "nama": p.get("NamaEmiten"),
                    "kegiatan_usaha": p.get("KegiatanUsahaUtama"),
                    "sektor": p.get("Sektor"),
                    "industri": p.get("Industri"),
                    "sub_industri": p.get("SubIndustri"),
                    "alamat": p.get("Alamat"),
                    "website": p.get("Website"),
                    "papan": p.get("PapanPencatatan"),
                    "tanggal_ipo": p.get("TanggalPencatatan"),
                    "pemegang_saham": data.get("PemegangSaham") or [],
                    "direktur": data.get("Direktur") or [],
                    "komisaris": data.get("Komisaris") or [],
                }

            last_err = "respons kosong"

        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:80]}"

    raise RuntimeError(last_err)


# ==========================================================
# YAHOO FINANCE
# ==========================================================

def fetch_yf_raw(kode: str) -> dict:
    """Ambil deskripsi bisnis + agregat kepemilikan dari Yahoo Finance.

    Retry dengan backoff karena YFRateLimitError sering transient.
    Raise Exception kalau semua percobaan gagal.
    """
    import yfinance as yf

    try:
        from curl_cffi import requests as creq
        session = creq.Session(impersonate="chrome")
    except Exception:
        session = None

    t = None
    info = {}
    last_err = None

    for wait in (0, 2, 5):
        if wait:
            time.sleep(wait)

        try:
            try:
                t = yf.Ticker(f"{kode}.JK", session=session)
                info = t.info or {}
            except TypeError:
                t = yf.Ticker(f"{kode}.JK")
                info = t.info or {}

            if info and (
                info.get("longBusinessSummary") is not None
                or info.get("marketCap") is not None
            ):
                break

            last_err = RuntimeError("info kosong dari Yahoo")

        except Exception as e:
            last_err = e

    if not info or (
        info.get("longBusinessSummary") is None
        and info.get("marketCap") is None
    ):
        raise last_err or RuntimeError("info kosong dari Yahoo")

    holders = {}
    try:
        mh = t.major_holders
        if mh is not None and not mh.empty:
            if "Value" in mh.columns:
                for k, v in mh["Value"].items():
                    holders[str(k)] = v
            else:
                for _, r in mh.iterrows():
                    holders[str(r.iloc[1])] = r.iloc[0]
    except Exception:
        pass

    officers = []
    for o in info.get("companyOfficers") or []:
        if o.get("name"):
            officers.append({
                "Nama": o.get("name"),
                "Jabatan": o.get("title", "-"),
            })

    return {
        "summary": info.get("longBusinessSummary"),
        "market_cap": info.get("marketCap"),
        "employees": info.get("fullTimeEmployees"),
        "insider_pct": holders.get("insidersPercentHeld"),
        "institution_pct": holders.get("institutionsPercentHeld"),
        "officers": officers,
    }
