# ==========================================================
# 🏢 COMPANY PROFILE & OWNERSHIP
# ==========================================================
# Urutan sumber data:
# 1. Snapshot harian (data/company_profiles_cache.parquet) — hasil
#    refresh otomatis GitHub Actions dari IDX + Yahoo Finance.
#    Cepat, tidak pernah kena blokir IP / rate limit karena tidak
#    fetch live dari Streamlit Cloud.
# 2. Live-fetch langsung ke IDX & Yahoo Finance — fallback untuk
#    emiten yang belum sempat masuk snapshot (baru IPO) atau kalau
#    snapshot belum pernah dibuat sama sekali.
# ==========================================================

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from . import profile_cache
from .idx_fetch import fetch_idx_raw, fetch_yf_raw


# ==========================================================
# LIVE FETCH (CACHED DI SESI — kegagalan TIDAK di-cache)
# ==========================================================

@st.cache_data(ttl=86400, show_spinner=False)
def _live_idx(kode: str):
    return fetch_idx_raw(kode)


def fetch_idx_profile(kode: str):
    """Return (dict, None) jika sukses, (None, pesan_error) jika gagal."""
    try:
        return _live_idx(kode), None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=86400, show_spinner=False)
def _live_yf(kode: str):
    return fetch_yf_raw(kode)


def fetch_yf_profile(kode: str):
    """Return (dict, None) jika sukses, (None, pesan_error) jika gagal."""
    try:
        return _live_yf(kode), None
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

        # ---------- 1. SNAPSHOT DULU ----------
        idx, yf_data, updated_at = profile_cache.read_snapshot(kode)
        idx_err = yf_err = None
        from_snapshot = idx is not None or yf_data is not None

        if from_snapshot:
            caption = "📦 Data dari snapshot harian"
            if updated_at:
                try:
                    dt = pd.to_datetime(updated_at)
                    caption += f" ({dt.strftime('%d %b %Y')})"
                    if datetime.now() - dt.to_pydatetime().replace(tzinfo=None) > timedelta(days=3):
                        caption += " ⚠️ agak lama, mungkin job refresh sedang bermasalah"
                except Exception:
                    pass
            st.caption(caption)

        # ---------- 2. FALLBACK: LIVE FETCH ----------
        else:
            with st.spinner("Mengambil profil perusahaan dari IDX..."):
                idx, idx_err = fetch_idx_profile(kode)
                yf_data, yf_err = fetch_yf_profile(kode)

        if idx is None and yf_data is None:
            st.info("Profil perusahaan tidak tersedia untuk emiten ini.")
            if not from_snapshot:
                st.caption(f"Detail — IDX: {idx_err} | Yahoo Finance: {yf_err}")
            return

        if idx is None and not from_snapshot:
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
