# ==========================================================
# 🏢 COMPANY PROFILE & OWNERSHIP (INSIDER)
# ==========================================================
# Menampilkan deskripsi profil perusahaan dan struktur
# kepemilikan (insider vs institusi vs publik) dari Yahoo
# Finance untuk halaman Stock Analysis.
# ==========================================================

import pandas as pd
import streamlit as st


# ==========================================================
# FETCH (CACHED)
# ==========================================================

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_company_profile(kode: str):
    """Ambil profil + data kepemilikan dari yfinance.

    Return dict, atau None jika data tidak bisa diambil.
    """
    import yfinance as yf

    symbol = f"{kode}.JK"

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
    except Exception:
        return None

    if not info:
        return None

    # ---------- STRUKTUR KEPEMILIKAN ----------
    holders = {}
    try:
        mh = t.major_holders
        if mh is not None and not mh.empty:
            if "Value" in mh.columns:
                # format yfinance baru: index = Breakdown
                for k, v in mh["Value"].items():
                    holders[str(k)] = v
            else:
                # format lama: kolom 0 = nilai, kolom 1 = label
                for _, r in mh.iterrows():
                    holders[str(r.iloc[1])] = r.iloc[0]
    except Exception:
        pass

    # ---------- INSTITUTIONAL HOLDERS ----------
    inst_df = pd.DataFrame()
    try:
        raw = t.institutional_holders
        if raw is not None and not raw.empty:
            inst_df = raw
    except Exception:
        pass

    # ---------- DIREKSI / MANAJEMEN (INSIDER) ----------
    officers = []
    for o in info.get("companyOfficers") or []:
        if o.get("name"):
            officers.append({
                "Nama": o.get("name"),
                "Jabatan": o.get("title", "-"),
            })

    return {
        "summary": info.get("longBusinessSummary"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "website": info.get("website"),
        "employees": info.get("fullTimeEmployees"),
        "market_cap": info.get("marketCap"),
        "insider_pct": holders.get("insidersPercentHeld"),
        "institution_pct": holders.get("institutionsPercentHeld"),
        "institution_count": holders.get("institutionsCount"),
        "institutional_holders": inst_df,
        "officers": officers,
    }


# ==========================================================
# HELPERS
# ==========================================================

def _fmt_market_cap(mcap):
    if not mcap:
        return "-"
    if mcap >= 1_000_000_000_000:
        return f"Rp {mcap / 1_000_000_000_000:,.1f} T"
    return f"Rp {mcap / 1_000_000_000:,.1f} M"


def _fmt_pct(val):
    if val is None:
        return None
    return round(float(val) * 100, 2)


# ==========================================================
# RENDER UI
# ==========================================================

def render_company_profile(kode: str):

    with st.expander("🏢 Profil Perusahaan & Kepemilikan", expanded=False):

        with st.spinner("Mengambil profil perusahaan..."):
            data = fetch_company_profile(kode)

        if data is None:
            st.info("Profil perusahaan tidak tersedia untuk emiten ini.")
            return

        # ================= DESKRIPSI =================
        if data["summary"]:
            st.markdown("#### 📄 Deskripsi Perusahaan")
            st.write(data["summary"])
        else:
            st.caption("Deskripsi perusahaan tidak tersedia.")

        # ================= INFO SINGKAT =================
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Market Cap", _fmt_market_cap(data["market_cap"]))
        c2.metric(
            "Karyawan",
            f"{data['employees']:,}" if data["employees"] else "-",
        )
        c3.metric("Sektor", data["sector"] or "-")
        c4.metric("Industri", data["industry"] or "-")

        if data["website"]:
            st.caption(f"🌐 Website: {data['website']}")

        st.divider()

        # ================= STRUKTUR KEPEMILIKAN =================
        st.markdown("#### 🧑‍💼 Struktur Kepemilikan")

        insider = _fmt_pct(data["insider_pct"])
        institution = _fmt_pct(data["institution_pct"])

        if insider is None and institution is None:
            st.info("Data kepemilikan tidak tersedia untuk emiten ini.")
        else:
            insider = insider or 0.0
            institution = institution or 0.0
            public = max(0.0, round(100 - insider - institution, 2))

            m1, m2, m3 = st.columns(3)
            m1.metric("Insider / Pengendali", f"{insider:.2f}%")
            m2.metric("Institusi", f"{institution:.2f}%")
            m3.metric("Publik & Lainnya", f"{public:.2f}%")

            if data["institution_count"]:
                st.caption(
                    f"Jumlah institusi tercatat: "
                    f"{int(data['institution_count']):,}"
                )

            # Donut chart komposisi
            import plotly.graph_objects as go

            fig = go.Figure(go.Pie(
                labels=["Insider / Pengendali", "Institusi", "Publik & Lainnya"],
                values=[insider, institution, public],
                hole=0.5,
                marker=dict(colors=["#ef4444", "#3b82f6", "#22c55e"]),
                textinfo="label+percent",
                hovertemplate="%{label}: %{value:.2f}%<extra></extra>",
            ))
            fig.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            st.caption(
                "ℹ️ *Insider* versi Yahoo Finance mencakup pemegang saham "
                "pengendali dan manajemen internal perusahaan."
            )

        # ================= DIREKSI / MANAJEMEN =================
        if data["officers"]:
            st.divider()
            st.markdown("#### 👔 Manajemen & Direksi (Insider)")
            st.dataframe(
                pd.DataFrame(data["officers"]),
                use_container_width=True,
                hide_index=True,
            )

        # ================= INSTITUTIONAL HOLDERS =================
        inst_df = data["institutional_holders"]
        if inst_df is not None and not inst_df.empty:
            st.divider()
            st.markdown("#### 🏦 Pemegang Saham Institusi Tercatat")

            show = inst_df.copy()
            if "pctHeld" in show.columns:
                show["pctHeld"] = (show["pctHeld"] * 100).round(4)
                show = show.rename(columns={"pctHeld": "Kepemilikan (%)"})
            show = show.rename(columns={
                "Date Reported": "Tanggal Lapor",
                "Holder": "Institusi",
                "Shares": "Jumlah Saham",
                "Value": "Nilai",
            })

            st.dataframe(show, use_container_width=True, hide_index=True)
