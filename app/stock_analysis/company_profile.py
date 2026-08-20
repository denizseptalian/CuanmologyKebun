# ==========================================================
# 🏢 COMPANY PROFILE & OWNERSHIP
# ==========================================================
# Sumber utama : API resmi IDX (idx.co.id) — pemegang saham
#                per nama + persentase, direksi, komisaris,
#                profil perusahaan berbahasa Indonesia.
# Fallback     : Yahoo Finance (deskripsi bisnis, market cap,
#                agregat kepemilikan) jika IDX tidak bisa
#                diakses dari server.
# ==========================================================

import pandas as pd
import streamlit as st

IDX_PROFILE_URL = (
    "https://www.idx.co.id/primary/ListedCompany/"
    "GetCompanyProfilesDetail?KodeEmiten={kode}&language=id-id"
)


# ==========================================================
# FETCH IDX (CACHED — kegagalan TIDAK di-cache)
# ==========================================================

@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_idx_cached(kode: str):
    # Exception tidak di-cache oleh st.cache_data, jadi kegagalan
    # sementara (situs down / diblokir) akan dicoba ulang di rerun
    # berikutnya, bukan tersimpan 24 jam.
    from curl_cffi import requests as creq

    last_err = "unknown"

    for imp in ("chrome", "safari", "edge"):
        try:
            r = creq.get(
                IDX_PROFILE_URL.format(kode=kode),
                impersonate=imp,
                timeout=15,
            )

            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
                continue

            data = r.json()

            if data.get("Profiles"):
                return data

            last_err = "respons kosong"

        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:80]}"

    raise RuntimeError(last_err)


def fetch_idx_profile(kode: str):
    """Ambil profil + pemegang saham + pengurus dari API IDX.

    Return (dict, None) jika sukses, (None, pesan_error) jika gagal.
    """
    try:
        data = _fetch_idx_cached(kode)
    except Exception as e:
        return None, str(e)

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
    }, None


# ==========================================================
# FETCH YAHOO FINANCE (CACHED) — deskripsi & fallback
# ==========================================================

@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_yf_cached(kode: str):
    import yfinance as yf

    # Sesi curl_cffi menyamar sebagai Chrome — tanpa ini Yahoo
    # sering menolak request dari IP datacenter (Streamlit Cloud)
    try:
        from curl_cffi import requests as creq
        session = creq.Session(impersonate="chrome")
    except Exception:
        session = None

    try:
        t = yf.Ticker(f"{kode}.JK", session=session)
        info = t.info or {}
    except TypeError:
        # yfinance versi lama tanpa parameter session
        t = yf.Ticker(f"{kode}.JK")
        info = t.info or {}

    if not info or (
        info.get("longBusinessSummary") is None
        and info.get("marketCap") is None
    ):
        raise RuntimeError("info kosong dari Yahoo")

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

    # return dict polos supaya aman di-pickle oleh st.cache_data
    return {
        "summary": info.get("longBusinessSummary"),
        "market_cap": info.get("marketCap"),
        "employees": info.get("fullTimeEmployees"),
        "insider_pct": holders.get("insidersPercentHeld"),
        "institution_pct": holders.get("institutionsPercentHeld"),
        "officers": officers,
    }


def fetch_yf_profile(kode: str):
    """Return (dict, None) jika sukses, (None, pesan_error) jika gagal."""
    try:
        return _fetch_yf_cached(kode), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"


# ==========================================================
# HELPERS
# ==========================================================

def _fmt_market_cap(mcap):
    if not mcap:
        return "-"
    if mcap >= 1_000_000_000_000:
        return f"Rp {mcap / 1_000_000_000_000:,.1f} T"
    return f"Rp {mcap / 1_000_000_000:,.1f} M"


def _fmt_shares(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return "-"


def _fmt_tanggal(iso):
    if not iso:
        return "-"
    try:
        return pd.to_datetime(iso).strftime("%d %b %Y")
    except Exception:
        return str(iso)


# ==========================================================
# RENDER UI
# ==========================================================

def render_company_profile(kode: str):

    with st.expander("🏢 Profil Perusahaan & Kepemilikan", expanded=False):

        with st.spinner("Mengambil profil perusahaan dari IDX..."):
            idx, idx_err = fetch_idx_profile(kode)
            yf_data, yf_err = fetch_yf_profile(kode)

        if idx is None and yf_data is None:
            st.info("Profil perusahaan tidak tersedia untuk emiten ini.")
            st.caption(f"Detail — IDX: {idx_err} | Yahoo Finance: {yf_err}")
            return

        if idx is None:
            st.caption(
                f"⚠️ Data pemegang saham per-nama dari IDX tidak dapat "
                f"diakses saat ini ({idx_err}) — menampilkan data agregat "
                f"dari Yahoo Finance sebagai gantinya."
            )

        # ================= DESKRIPSI =================
        st.markdown("#### 📄 Company Overview")

        if yf_data and yf_data.get("summary"):
            st.write(yf_data["summary"])
        elif idx and idx.get("kegiatan_usaha"):
            st.write(idx["kegiatan_usaha"])
        else:
            st.caption("Deskripsi perusahaan tidak tersedia.")

        # ================= INFO SINGKAT =================
        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Market Cap",
            _fmt_market_cap(yf_data["market_cap"]) if yf_data else "-",
        )

        if idx:
            c2.metric("Sektor", idx["sektor"] or "-")
            c3.metric("Papan", idx["papan"] or "-")
            c4.metric("Listing", _fmt_tanggal(idx["tanggal_ipo"]))

            det1, det2 = st.columns(2)
            with det1:
                if idx["kegiatan_usaha"]:
                    st.caption(f"**Kegiatan usaha:** {idx['kegiatan_usaha']}")
                if idx["industri"]:
                    st.caption(f"**Industri:** {idx['industri']}")
            with det2:
                if idx["website"]:
                    st.caption(f"🌐 {idx['website']}")
                if idx["alamat"]:
                    alamat = " ".join(str(idx["alamat"]).split())
                    st.caption(f"📍 {alamat}")
        elif yf_data:
            c2.metric(
                "Karyawan",
                f"{yf_data['employees']:,}" if yf_data["employees"] else "-",
            )

        st.divider()

        # ==========================================================
        # PEMEGANG SAHAM (DATA IDX — PER NAMA + PERSENTASE)
        # ==========================================================
        if idx and idx["pemegang_saham"]:

            st.markdown("#### 🧑‍💼 Pemegang Saham")
            st.caption("Sumber: IDX (Bursa Efek Indonesia)")

            rows = []
            for s in idx["pemegang_saham"]:
                jumlah = s.get("Jumlah") or 0
                pct = s.get("Persentase") or 0
                if jumlah <= 0 and pct <= 0:
                    continue
                rows.append({
                    "Nama": s.get("Nama", "-"),
                    "Kategori": s.get("Kategori", "-"),
                    "Jumlah Saham": _fmt_shares(jumlah),
                    "Persentase": f"{pct:.2f}%",
                    "Pengendali": "✅" if s.get("Pengendali") else "",
                    "_pct": pct,
                })

            if rows:
                df_ps = (
                    pd.DataFrame(rows)
                    .sort_values("_pct", ascending=False)
                    .drop(columns="_pct")
                )

                st.dataframe(
                    df_ps,
                    use_container_width=True,
                    hide_index=True,
                )

                # Donut komposisi kepemilikan
                donut = [(r["Nama"], r["_pct"]) for r in rows if r["_pct"] > 0]

                if donut:
                    import plotly.graph_objects as go

                    fig = go.Figure(go.Pie(
                        labels=[d[0] for d in donut],
                        values=[d[1] for d in donut],
                        hole=0.5,
                        textinfo="label+percent",
                        hovertemplate="%{label}: %{value:.2f}%<extra></extra>",
                    ))
                    fig.update_layout(
                        height=340,
                        margin=dict(l=10, r=10, t=10, b=10),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

        elif yf_data:
            # -------- fallback agregat Yahoo Finance --------
            st.markdown("#### 🧑‍💼 Struktur Kepemilikan (agregat)")
            st.caption(
                "Data per-nama dari IDX tidak dapat diakses — "
                "menampilkan agregat dari Yahoo Finance."
            )

            insider = yf_data.get("insider_pct")
            institution = yf_data.get("institution_pct")

            if insider is None and institution is None:
                st.info("Data kepemilikan tidak tersedia.")
            else:
                insider = round((insider or 0) * 100, 2)
                institution = round((institution or 0) * 100, 2)
                public = max(0.0, round(100 - insider - institution, 2))

                m1, m2, m3 = st.columns(3)
                m1.metric("Insider / Pengendali", f"{insider:.2f}%")
                m2.metric("Institusi", f"{institution:.2f}%")
                m3.metric("Publik & Lainnya", f"{public:.2f}%")

        # ==========================================================
        # DIREKSI & KOMISARIS
        # ==========================================================
        direksi = (idx or {}).get("direktur") or []
        komisaris = (idx or {}).get("komisaris") or []

        if direksi or komisaris:
            st.divider()
            col_d, col_k = st.columns(2)

            with col_d:
                st.markdown("#### 👔 Direksi")
                if direksi:
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "Nama": d.get("Nama", "-"),
                                "Jabatan": str(d.get("Jabatan", "-")).title(),
                                "Afiliasi": "✅" if d.get("Afiliasi") else "",
                            }
                            for d in direksi
                        ]),
                        use_container_width=True,
                        hide_index=True,
                    )

            with col_k:
                st.markdown("#### 🎓 Komisaris")
                if komisaris:
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "Nama": k.get("Nama", "-"),
                                "Jabatan": str(k.get("Jabatan", "-")).title(),
                                "Independen": "✅" if k.get("Independen") else "",
                            }
                            for k in komisaris
                        ]),
                        use_container_width=True,
                        hide_index=True,
                    )

        elif yf_data and yf_data.get("officers"):
            st.divider()
            st.markdown("#### 👔 Manajemen & Direksi")
            st.dataframe(
                pd.DataFrame(yf_data["officers"]),
                use_container_width=True,
                hide_index=True,
            )
