import os
import streamlit as st

from .helpers import (
    calc_minor_support,
    clean_price_df,
    format_money,
    format_number
)

from .smart_money import calculate_smart_money
from .engine import (
    calculate_gap_fill_rate,
    get_support_levels,
    get_entry_plan
)

from app.utils.news_engine import fetch_stock_news
from app.utils.market_data import load_price_data
from app.renderers.telegram_stock_analysis import render_stock_analysis_message
from app.services.telegram_bot import send_message

# ==========================================================
# 📊 MAIN STOCK ANALYSIS UI
# ==========================================================
def render_stock_analysis():

    from app.utils.market_data import load_price_data
    from app.utils.analysis_engine import analyze_single_stock
    from app.config.saham_list import SAHAM_LIST
    from app.config.saham_profile import SAHAM_PROFILE
    from app.utils.sector_utils import get_sector_badge
    from datetime import datetime, timedelta
    import pandas as pd

    st.header("📊 Stock Analysis")
    st.caption("Analisa mandiri satu saham (independen dari screener)")

    # ================= INPUT =================
    col1, col2 = st.columns([2, 1])

    with col1:
        kode = st.selectbox("Kode Saham", SAHAM_LIST, key="analysis_kode")

    with col2:
        timeframe = st.selectbox("Timeframe", ["Weekly"], key="analysis_tf")

    # ================= RESET =================
    def reset_analysis_state():

        for k in [

            "analysis_result",
            "analysis_df",
            "news_result",
            "analyzed",

        ]:

            st.session_state.pop(k, None)

    if st.session_state.get("last_analysis_kode") != kode:
        reset_analysis_state()
        st.session_state.last_analysis_kode = kode

    if st.session_state.get("last_analysis_tf") != timeframe:
        reset_analysis_state()
        st.session_state.last_analysis_tf = timeframe

    # ================= PROFILE =================
    company_name = SAHAM_PROFILE.get(kode, kode)
    sector_emoji, sector_name = get_sector_badge(kode)

    st.markdown(f"### {sector_emoji} {company_name} ({kode})")
    st.caption(f"Sektor: {sector_name}")

    # ================= ANALYZE =================
    if st.button("🔍 Analyze Stock"):

        df = load_price_data(kode)

        if df.empty:

            st.warning("Data harga tidak tersedia.")

        else:

            # ==========================================================
            # MAIN ANALYSIS
            # ==========================================================

            result = analyze_single_stock(df)

            result["minor_support"] = calc_minor_support(df)

            # ==========================================================
            # NEWS (basic)
            # ==========================================================

            news_result = fetch_stock_news(kode)

            # ==========================================================
            # GOOGLE NEWS SENTIMENT (detail)
            # ==========================================================

            from datetime import datetime, timedelta
            from app.utils.sentiment_analysis import smart_keyword, get_news

            _, _, kw_encoded = smart_keyword("", kode)
            sent_start = (datetime.now() - timedelta(days=30)).date()
            sent_end   = datetime.now().date()
            gn_result  = get_news(kw_encoded, sent_start, sent_end)

            # ==========================================================
            # SAVE SESSION
            # ==========================================================

            st.session_state["analysis_result"] = result
            st.session_state["analysis_df"]     = df
            st.session_state["news_result"]      = news_result
            st.session_state[f"sent_result_{kode}"] = gn_result

    if "analysis_result" not in st.session_state:
        return

    result = st.session_state["analysis_result"]

    df_price = clean_price_df(st.session_state["analysis_df"])
    news_result = st.session_state.get("news_result", {})

    # ================= MARKET =================
    st.subheader("🧭 Market Condition")

    last_price = df_price["CLOSE"].iloc[-1]

    ma200 = df_price["CLOSE"].rolling(200).mean().iloc[-1] if len(df_price) >= 200 else None
    ma50 = df_price["CLOSE"].rolling(50).mean().iloc[-1] if len(df_price) >= 50 else None
    std = df_price["CLOSE"].rolling(200).std().iloc[-1] if len(df_price) >= 200 else None

    z_score = (last_price - ma200) / std if ma200 and std else None

    # ================= FAIR RANGE =================
    if ma200 and std:
        fair_low = ma200 - std
        fair_high = ma200 + std
    else:
        fair_low, fair_high = None, None

    trend = result.get("trend", "-")
    st.markdown(f"### {trend}")

    # ======================================================
    # CLEAN COLUMNS
    # ======================================================

    df_price.columns = [
        c[0] if isinstance(c, tuple) else c
        for c in df_price.columns
    ]

    df_price.columns = [
        str(c).upper()
        for c in df_price.columns
    ]

    # ======================================================
    # ATR
    # ======================================================

    high = df_price["HIGH"]
    low = df_price["LOW"]

    atr_pct = (
        (
            high.tail(14).max()
            - low.tail(14).min()
        )
        / max(last_price, 1)
    ) * 100

    # ================= PRICE INFO =================
    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Last Price",
            f"Rp {int(last_price):,}".replace(",", ".")
        )

    with c2:
        if ma200:
            st.metric(
                "Fair Value (MA200)",
                f"Rp {int(ma200):,}".replace(",", ".")
            )
        else:
            st.metric("Fair Value", "-")

    with c3:
        st.metric(
            "Volatility",
            f"{atr_pct:.1f}%"
        )
    # ================= RANGE =================
    if fair_low and fair_high:
        st.caption(
            f"Range Wajar: Rp {int(fair_low):,} - Rp {int(fair_high):,}".replace(",", ".")
        )

    # ================= VALUATION =================
    if z_score is not None:
        if z_score < -1:
            fv_status = "🟢 Undervalued"
        elif z_score > 1:
            fv_status = "🔴 Overvalued"
        else:
            fv_status = "⚖️ Fair"
    else:
        fv_status = "-"

    st.markdown(f"**Status: {fv_status}**")

    # ===================== SUPPORT & RESISTANCE =====================
    st.subheader("📉 Support & Resistance")

    last_price = df_price["CLOSE"].iloc[-1]

    major_support = result.get("support")
    minor_support = calc_minor_support(df_price)

    # 🔹 Micro support (very near)
    low_col = None

    for col in df_price.columns:
        if "low" in col.lower():
            low_col = col
            break

    if low_col:
        micro_support = int(df_price[low_col].tail(7).min()) if len(df_price) >= 7 else None
    else:
        micro_support = None

    supports = []

    if micro_support:
        supports.append(("Micro", micro_support))
    if minor_support:
        supports.append(("Minor", minor_support))
    if major_support:
        supports.append(("Major", major_support))

    # sort by nearest
    supports_sorted = sorted(
        supports,
        key=lambda x: abs(last_price - x[1])
    )

    rows = []

    labels = ["Near", "Mid", "Far"]

    for i, (label, price) in enumerate(supports_sorted[:3]):
        rows.append(
            (
                f"Support ({labels[i]})",
                f"Rp {int(price):,} ({label})".replace(",", "."),
            )
        )

    # resistance
    if result.get("resistance"):
        rows.append(
            (
                "Resistance",
                f"Rp {int(result['resistance']):,}".replace(",", "."),
            )
        )

    sr_df = pd.DataFrame(rows, columns=["Level", "Price"])
    st.table(sr_df.set_index("Level"))


    # ===================== ENTRY PLAN =====================
    st.subheader("🎯 Entry Plan")

    # ================= BASIC DATA =================
    last_price = df_price["CLOSE"].iloc[-1]

    major_support = result.get("support")
    minor_support = calc_minor_support(df_price)

    # ================= MICRO SUPPORT =================
    low_col = next((col for col in df_price.columns if "low" in col.lower()), None)

    if low_col and len(df_price) >= 7:
        micro_support = float(df_price[low_col].tail(7).min())
    else:
        micro_support = None

    # ================= BUILD SUPPORT =================
    supports = []

    if micro_support is not None:
        supports.append(("Micro", micro_support))
    if minor_support is not None:
        supports.append(("Minor", minor_support))
    if major_support is not None:
        supports.append(("Major", major_support))

    if not supports:
        st.warning("Support tidak tersedia")
    else:
        supports_sorted = sorted(
            supports,
            key=lambda x: abs(last_price - x[1])
        )

        near_support = supports_sorted[0][1]
        deep_support = supports_sorted[1][1] if len(supports_sorted) > 1 else near_support

        # ================= TICK =================
        def round_to_tick(price):
            if price < 200:
                tick = 1
            elif price < 500:
                tick = 2
            elif price < 2000:
                tick = 5
            elif price < 5000:
                tick = 10
            else:
                tick = 25
            return int(round(price / tick) * tick)

        # ================= ENTRY =================
        entry_near_low = round_to_tick(near_support * 0.99)
        entry_near_high = round_to_tick(near_support * 1.01)

        entry_deep_low = round_to_tick(deep_support * 0.97)
        entry_deep_high = round_to_tick(deep_support * 1.00)

        sl = round_to_tick(deep_support * 0.97)

        risk_pct = ((last_price - sl) / last_price) * 100

        def fmt(x):
            return f"Rp {format_number(x)}"

        entry_df = pd.DataFrame({
            "Parameter": [
                "Entry Near (Pullback)",
                "Entry Deep (Discount)",
                "Stop Loss",
                "Risk",
            ],
            "Value": [
                f"{fmt(entry_near_low)} – {fmt(entry_near_high)}",
                f"{fmt(entry_deep_low)} – {fmt(entry_deep_high)}",
                fmt(sl),
                f"{risk_pct:.1f} %",
            ]
        })

        st.table(entry_df.set_index("Parameter"))

    # ================= GAP ANALYSIS =================
    st.subheader("📊 Gap Analysis")

    df_gap = load_price_data(kode)
    df_gap = clean_price_df(df_gap)

    if df_gap is None or df_gap.empty:
        st.warning("Data gap tidak tersedia")

    else:
        last_price = df_gap["CLOSE"].iloc[-1]

        gaps = []

        # ================= FVG DETECTION =================
        for i in range(2, len(df_gap)):
            c1_high = df_gap.iloc[i - 2]["HIGH"]
            c1_low = df_gap.iloc[i - 2]["LOW"]

            c3_high = df_gap.iloc[i]["HIGH"]
            c3_low = df_gap.iloc[i]["LOW"]

            date = df_gap.index[i]

            # Bullish gap
            if c3_low > c1_high:
                gap_low = c1_high
                gap_high = c3_low

                if (gap_high - gap_low) / gap_low > 0.015:
                    gaps.append({"low": gap_low, "high": gap_high, "date": date})

            # Bearish gap
            elif c3_high < c1_low:
                gap_low = c3_high
                gap_high = c1_low

                if (gap_high - gap_low) / gap_low > 0.015:
                    gaps.append({"low": gap_low, "high": gap_high, "date": date})

        # ================= SORT & MERGE =================
        gaps = sorted(gaps, key=lambda x: x["date"])

        merged = []

        for g in gaps:
            if not merged:
                merged.append(g)
                continue

            last = merged[-1]

            if abs(g["low"] - last["high"]) / last["high"] < 0.03:
                last["low"] = min(last["low"], g["low"])
                last["high"] = max(last["high"], g["high"])
                last["date"] = g["date"]
            else:
                merged.append(g)

        # ================= AMBIL TERBAIK =================
        gaps = merged[-10:]

        gaps = sorted(
            gaps,
            key=lambda g: abs(((g["low"] + g["high"]) / 2) - last_price)
        )[:3]

        def fmt_price(x):
            return f"Rp {format_number(round_to_tick(x))}"

        def fmt_date(d):
            return d.strftime("%d-%b-%Y")

        rows = []

        for g in gaps:
            mid = (g["low"] + g["high"]) / 2

            label = "Gap Atas" if mid > last_price else "Gap Bawah"

            dist = abs(mid - last_price) / last_price

            rows.append((
                label,
                f"{fmt_price(g['low'])} – {fmt_price(g['high'])}",
                fmt_date(g["date"]),
                f"{dist*100:.1f}%"
            ))

        if rows:
            gap_df = pd.DataFrame(
                rows,
                columns=["Type", "Range", "Tanggal", "Distance"]
            )
            st.table(gap_df.set_index("Type"))
        else:
            st.caption("Tidak ada gap signifikan")

    # ================= SMART MONEY =================
    st.subheader("💰 Smart Money Flow (10D)")

    result_sm = calculate_smart_money(df_price)

    if result_sm:
        summary = result_sm["summary"]
        table = result_sm["table"].copy()

        col1, col2, col3 = st.columns(3)

        col1.metric("Smart Money", f"{summary['smart']/1e9:.2f} B")
        col2.metric("Clean Money", f"{summary['clean']/1e9:.2f} B")
        col3.metric("Power", f"{summary['power']}%")

        st.markdown(f"**Status: {summary['status']}**")

        if "Date" not in table.columns:
            table["Date"] = table.index.astype(str)

        table["Tx"] = table.get("VOLUME", 0).apply(format_number)
        table["Value"] = table.get("VALUE", 0).apply(format_money)
        table["Smart"] = table.get("SMART", 0).apply(format_money)
        table["Bad"] = table.get("BAD", 0).apply(format_money)
        table["Clean"] = table.get("CLEAN", 0).apply(format_money)

        table["Gain%"] = table.get("GAIN (%)", 0).apply(lambda x: f"{x:.2f}%")
        table["AVP"] = table.get("AVP", 0).astype(int)
        table["RCV"] = table.get("RCV", 0).astype(int)
        table["📊"] = table.get("SIGNAL", "-")

        final_cols = [
            col for col in [
                "Date","Tx","Value","AVP","Gain%","Smart","Bad","Clean","RCV","📊"
            ] if col in table.columns
        ]

        table = table[final_cols]

        table = table.reset_index(drop=True)
        table.index += 1

        st.dataframe(table, use_container_width=True)

        st.caption(
            f"RCV: {summary['avg_rcv']} | Win Rate: {summary['win_rate']}/10 "
            f"{'⬆️' if summary['trend_up'] else '⬇️'}"
        )

    # ===================== ALIRAN DANA ASING & RETAIL =====================
    st.subheader("🌏 Aliran Dana Asing vs Retail")

    import plotly.graph_objects as go
    from app.utils.broker_flow import (
        calc_flow_from_price,
        summarize_flow_from_price,
    )

    # Ambil data harga harian (lebih panjang untuk trend)
    from app.core.data_loader import load_daily_data
    df_daily_raw = load_daily_data(kode, period="3mo")
    if df_daily_raw is None or df_daily_raw.empty:
        df_daily_raw = df_price.copy()

    df_flow = calc_flow_from_price(df_daily_raw, days=60)

    if df_flow is None or df_flow.empty:
        st.warning("Data aliran tidak tersedia untuk saham ini.")
    else:
        flow = summarize_flow_from_price(df_flow)

        # ─── METRICS ───────────────────────────────────────────────────
        st.markdown("#### 📊 Rata-rata Aliran Asing & Retail")
        st.caption(
            "Estimasi berbasis analisis Smart Volume Flow (VSA) — "
            "pola volume institusi vs retail dari data harga harian."
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Total Aliran Asing/Institusi",
            f"Rp {flow['total_asing']/1e12:.2f} T",
            delta="Dominan Beli" if flow["asing_trend_up"] else "Tren Menurun",
            delta_color="normal" if flow["asing_trend_up"] else "inverse",
        )
        c2.metric(
            "Rata-rata Harian (Asing)",
            f"Rp {flow['avg_asing']/1e9:.1f} B",
        )
        c3.metric(
            "Total Aliran Retail",
            f"Rp {abs(flow['total_retail'])/1e12:.2f} T",
            delta="Tekanan Jual" if flow["total_retail"] < 0 else "Akumulasi",
            delta_color="inverse" if flow["total_retail"] < 0 else "normal",
        )
        c4.metric(
            "Hari Dominasi Asing",
            f"{flow['asing_dominant_days']} / {flow['days']} hari",
        )

        st.divider()

        # ─── TABEL HARIAN (setiap hari breakdown asing vs retail) ─────
        st.markdown("#### 🗓️ Aliran Harian: Asing vs Retail per Sesi")

        df_tbl = df_flow.copy()
        df_tbl["Tanggal"]        = df_tbl["date"].dt.strftime("%d %b %Y")
        df_tbl["Harga Tutup"]    = df_tbl["close"].apply(lambda x: f"Rp {int(x):,}".replace(",", "."))
        df_tbl["Aliran Asing"]   = (df_tbl["asing_flow"] / 1e9).round(2).apply(lambda x: f"{x:.2f} B")
        df_tbl["Aliran Retail"]  = (df_tbl["retail_flow"] / 1e9).round(2).apply(lambda x: f"{x:.2f} B")
        df_tbl["Signal"]         = df_tbl["asing_flow"].apply(
            lambda x: "🟢 Asing Masuk" if x > df_flow["asing_flow"].mean() * 1.2
            else ("🔴 Asing Keluar" if x < df_flow["asing_flow"].mean() * 0.8 else "⚪ Normal")
        )

        st.dataframe(
            df_tbl[["Tanggal", "Harga Tutup", "Aliran Asing", "Aliran Retail", "Signal"]]
            .sort_values("Tanggal", ascending=False)
            .reset_index(drop=True),
            use_container_width=True,
            height=300,
        )

        st.divider()

        # ─── GRAFIK TREN KUMULATIF ASING vs RETAIL ────────────────────
        st.markdown("#### 📉 Grafik Penurunan / Tren Asing vs Retail")

        df_plot = df_flow.copy()
        df_plot["asing_kum"]  = df_plot["asing_flow"].cumsum()
        df_plot["retail_kum"] = df_plot["retail_flow"].cumsum()

        fig_trend = go.Figure()

        fig_trend.add_trace(go.Scatter(
            x=df_plot["date"],
            y=df_plot["asing_kum"] / 1e9,
            mode="lines",
            name="Asing/Institusi (Kumulatif)",
            line=dict(color="#ef4444", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(239,68,68,0.12)",
            hovertemplate="%{x|%d %b %Y}<br>Asing: Rp %{y:.1f} B<extra></extra>",
        ))

        fig_trend.add_trace(go.Scatter(
            x=df_plot["date"],
            y=df_plot["retail_kum"] / 1e9,
            mode="lines",
            name="Retail/Lokal (Kumulatif)",
            line=dict(color="#60a5fa", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(96,165,250,0.12)",
            hovertemplate="%{x|%d %b %Y}<br>Retail: Rp %{y:.1f} B<extra></extra>",
        ))

        fig_trend.add_hline(
            y=0,
            line_dash="dash",
            line_color="#6b7280",
            line_width=1,
        )

        fig_trend.update_layout(
            xaxis_title="Tanggal",
            yaxis_title="Net Flow Kumulatif (Miliar Rp)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=380,
            margin=dict(l=10, r=10, t=30, b=40),
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font=dict(color="#f1f5f9"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # ─── BAR HARIAN ASING vs RETAIL ───────────────────────────────
        st.markdown("**Aliran Harian Asing vs Retail (Net)**")

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_plot["date"],
            y=df_plot["asing_flow"] / 1e9,
            name="Asing",
            marker_color=[
                "#22c55e" if v >= 0 else "#ef4444"
                for v in df_plot["asing_flow"]
            ],
            hovertemplate="%{x|%d %b}<br>Asing: Rp %{y:.1f} B<extra></extra>",
        ))
        fig_bar.add_trace(go.Bar(
            x=df_plot["date"],
            y=df_plot["retail_flow"] / 1e9,
            name="Retail",
            marker_color=[
                "#60a5fa" if v >= 0 else "#fb923c"
                for v in df_plot["retail_flow"]
            ],
            hovertemplate="%{x|%d %b}<br>Retail: Rp %{y:.1f} B<extra></extra>",
        ))
        fig_bar.update_layout(
            barmode="group",
            xaxis_title="Tanggal",
            yaxis_title="Net Flow (Miliar Rp)",
            height=300,
            margin=dict(l=10, r=10, t=10, b=40),
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font=dict(color="#f1f5f9"),
            legend=dict(orientation="h", y=1.05),
            hovermode="x unified",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # ─── AKTIVITAS PER KODE BROKER ────────────────────────────────
        st.divider()
        st.markdown("#### 🏢 Aktivitas Per Kode Broker")
        st.caption(
            "⚠️ Estimasi pola aktivitas broker berdasarkan Smart Volume Flow (VSA) — "
            "bukan data transaksi broker IDX sesungguhnya. Gunakan sebagai referensi pola, bukan nilai absolut."
        )

        from app.utils.broker_flow import (
            calc_broker_tiers_from_price,
            summarize_broker_tiers,
            calc_per_broker_from_price,
        )

        df_tiers  = calc_broker_tiers_from_price(df_daily_raw, days=60)
        df_brokers = calc_per_broker_from_price(df_daily_raw, days=60, stock_code=kode)

        if df_brokers is None or df_brokers.empty:
            st.warning("Data broker tidak tersedia.")
        else:
            # ── Tab: Semua / Asing / Lokal ───────────────────────────
            tab_all, tab_asing, tab_lokal = st.tabs(["📊 Semua Broker", "🌏 Asing", "🏦 Lokal"])

            _DARK = dict(
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                font=dict(color="#f1f5f9"),
                margin=dict(l=10, r=10, t=40, b=10),
            )

            # Harga penutupan terakhir untuk referensi garis
            _last_close = int(df_tiers["close"].iloc[-1]) if df_tiers is not None and not df_tiers.empty else 0

            def _broker_bar(df_sub, title, n=20):
                df_sub = df_sub.sort_values("net").tail(n).copy()
                colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df_sub["net"]]
                label  = df_sub["code"] + " — " + df_sub["name"]
                fig = go.Figure(go.Bar(
                    x=df_sub["net"] / 1e9,
                    y=label,
                    orientation="h",
                    marker_color=colors,
                    customdata=df_sub[["buy", "sell", "avg_buy", "avg_sell", "avg_price", "type"]].values,
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        "Net: Rp %{x:.1f} B<br>"
                        "Est. Beli: Rp %{customdata[0]:,.0f}<br>"
                        "Est. Jual: Rp %{customdata[1]:,.0f}<br>"
                        "Avg Beli: Rp %{customdata[2]:,}<br>"
                        "Avg Jual: Rp %{customdata[3]:,}<br>"
                        "Avg Harga: Rp %{customdata[4]:,}<br>"
                        "Tipe: %{customdata[5]}"
                        "<extra></extra>"
                    ),
                ))
                fig.update_layout(
                    title=dict(text=title, font=dict(size=13)),
                    xaxis_title="Net Flow Estimasi (Miliar Rp)",
                    height=max(360, n * 30),
                    **_DARK,
                )
                fig.add_vline(x=0, line_dash="dash", line_color="#6b7280", line_width=1)
                return fig

            def _avg_price_chart(df_sub, title):
                """Scatter chart harga rata-rata beli vs jual per broker."""
                df_sub = df_sub.sort_values("avg_price").copy()
                label  = df_sub["code"] + " — " + df_sub["name"]
                colors_dot = ["#22c55e" if v >= 0 else "#ef4444" for v in df_sub["net"]]

                fig = go.Figure()

                # Garis avg_buy (diamond)
                fig.add_trace(go.Scatter(
                    x=df_sub["avg_buy"],
                    y=label,
                    mode="markers",
                    name="Avg Beli",
                    marker=dict(symbol="diamond", size=10, color="#22c55e"),
                    hovertemplate="<b>%{y}</b><br>Avg Beli: Rp %{x:,}<extra></extra>",
                ))
                # Garis avg_sell (circle)
                fig.add_trace(go.Scatter(
                    x=df_sub["avg_sell"],
                    y=label,
                    mode="markers",
                    name="Avg Jual",
                    marker=dict(symbol="circle", size=10, color="#ef4444"),
                    hovertemplate="<b>%{y}</b><br>Avg Jual: Rp %{x:,}<extra></extra>",
                ))
                # Garis avg_price keseluruhan (square)
                fig.add_trace(go.Scatter(
                    x=df_sub["avg_price"],
                    y=label,
                    mode="markers",
                    name="Avg Keseluruhan",
                    marker=dict(symbol="square", size=8, color="#f59e0b"),
                    hovertemplate="<b>%{y}</b><br>Avg Harga: Rp %{x:,}<extra></extra>",
                ))
                # Garis harga sekarang
                if _last_close > 0:
                    fig.add_vline(
                        x=_last_close,
                        line_dash="dash", line_color="#60a5fa", line_width=1.5,
                        annotation_text=f"  Harga Kini: {_last_close:,}",
                        annotation_font_color="#60a5fa",
                    )
                fig.update_layout(
                    title=dict(text=title, font=dict(size=13)),
                    xaxis_title="Estimasi Harga Rata-rata (Rp)",
                    height=max(360, len(df_sub) * 30),
                    legend=dict(orientation="h", y=1.05),
                    **_DARK,
                )
                return fig

            with tab_all:
                top_n = min(24, len(df_brokers))
                st.plotly_chart(
                    _broker_bar(df_brokers, f"Net Flow Estimasi — {top_n} Broker", n=top_n),
                    use_container_width=True,
                )
                st.plotly_chart(
                    _avg_price_chart(df_brokers, "Harga Rata-rata Per Broker (◆ Beli | ● Jual | ■ Rata-rata | ─ Harga Kini)"),
                    use_container_width=True,
                )

            with tab_asing:
                df_a = df_brokers[df_brokers["type"] == "Asing"].copy()
                st.plotly_chart(
                    _broker_bar(df_a, "Net Flow Estimasi — Broker Asing", n=len(df_a)),
                    use_container_width=True,
                )
                st.plotly_chart(
                    _avg_price_chart(df_a, "Harga Rata-rata — Broker Asing"),
                    use_container_width=True,
                )

            with tab_lokal:
                df_l = df_brokers[df_brokers["type"] == "Lokal"].copy()
                st.plotly_chart(
                    _broker_bar(df_l, "Net Flow Estimasi — Broker Lokal", n=len(df_l)),
                    use_container_width=True,
                )
                st.plotly_chart(
                    _avg_price_chart(df_l, "Harga Rata-rata — Broker Lokal"),
                    use_container_width=True,
                )

            # ── Tabel lengkap broker ──────────────────────────────────
            with st.expander("📋 Tabel Lengkap Aktivitas Per Broker", expanded=False):
                df_tbl_br = df_brokers.copy()
                df_tbl_br["Kode"]           = df_tbl_br["code"]
                df_tbl_br["Nama Broker"]    = df_tbl_br["name"]
                df_tbl_br["Tipe"]           = df_tbl_br["type"]
                df_tbl_br["Est. Beli (B)"]  = (df_tbl_br["buy"] / 1e9).round(2)
                df_tbl_br["Est. Jual (B)"]  = (df_tbl_br["sell"] / 1e9).round(2)
                df_tbl_br["Net (B)"]        = (df_tbl_br["net"] / 1e9).round(2)
                df_tbl_br["Avg Beli (Rp)"]  = df_tbl_br["avg_buy"].apply(lambda x: f"{int(x):,}".replace(",", "."))
                df_tbl_br["Avg Jual (Rp)"]  = df_tbl_br["avg_sell"].apply(lambda x: f"{int(x):,}".replace(",", "."))
                df_tbl_br["Avg Harga (Rp)"] = df_tbl_br["avg_price"].apply(lambda x: f"{int(x):,}".replace(",", "."))
                df_tbl_br["Aksi"]           = df_tbl_br["net"].apply(
                    lambda x: "🟢 Net Beli" if x > 0 else "🔴 Net Jual"
                )
                st.dataframe(
                    df_tbl_br[["Kode", "Nama Broker", "Tipe",
                                "Est. Beli (B)", "Est. Jual (B)", "Net (B)",
                                "Avg Beli (Rp)", "Avg Jual (Rp)", "Avg Harga (Rp)", "Aksi"]]
                    .sort_values("Net (B)", ascending=False)
                    .reset_index(drop=True),
                    use_container_width=True,
                    height=400,
                )

            # ── Tier summary (ringkas di bawah) ──────────────────────
            if df_tiers is not None and not df_tiers.empty:
                tier_stats = summarize_broker_tiers(df_tiers)
                st.divider()
                st.markdown("**Komposisi Sesi Trading (60 Hari)**")
                tc1, tc2, tc3 = st.columns(3)
                tc1.metric("🔴 Sesi Institusi/Asing",
                           f"{tier_stats['tier_a_days']} sesi ({tier_stats['tier_a_pct']}%)")
                tc2.metric("🟡 Sesi Mid/Fund",
                           f"{tier_stats['tier_b_days']} sesi ({tier_stats['tier_b_pct']}%)")
                tc3.metric("🔵 Sesi Retail",
                           f"{tier_stats['tier_c_days']} sesi ({tier_stats['tier_c_pct']}%)")

        # # ===================== CYCLE PROJECTION (SMART + ADAPTIVE) =====================
        # st.subheader("📅 Cycle Projection")

        # today = datetime.now().date()
        # cycle = result.get("cycle") if "result" in locals() else None

        # if not cycle:

        #     st.warning("Data cycle tidak tersedia")

        # else:

        #     import pandas as pd
        #     from datetime import timedelta

        #     # ==========================================================
        #     # HELPER
        #     # ==========================================================

        #     def safe_date(key):

        #         try:

        #             return datetime.strptime(
        #                 cycle.get(key, ""),
        #                 "%Y-%m-%d"
        #             ).date()

        #         except:

        #             return None

        #     def fmt(d):

        #         return (
        #             d.strftime("%d-%b-%Y")
        #             if d else "-"
        #         )

        #     def fmt_range(s, e):

        #         return (
        #             f"{fmt(s)} - {fmt(e)}"
        #         )

        #     def days_to(d):

        #         return (
        #             (d - today).days
        #             if d else None
        #         )

        #     def in_range(start, end):

        #         return (
        #             start
        #             and end
        #             and start <= today <= end
        #         )

        #     # ==========================================================
        #     # PARSE CYCLE
        #     # ==========================================================

        #     last_low = safe_date("last_low")

        #     near_low_start = safe_date("next_low_start")
        #     near_low_end = safe_date("next_low_end")

        #     next_low_start = safe_date("second_low_start")
        #     next_low_end = safe_date("second_low_end")

        #     near_high_start = safe_date("next_high_start")
        #     near_high_end = safe_date("next_high_end")

        #     next_high_start = safe_date("second_high_start")
        #     next_high_end = safe_date("second_high_end")

        #     # ==========================================================
        #     # DEFAULT
        #     # ==========================================================

        #     trend_mode = "sideways"

        #     atr_pct = 0

        #     cycle_confidence = 0

        #     # ==========================================================
        #     # LOAD PRICE DATA
        #     # ==========================================================

        #     df_price = st.session_state.get(
        #         "analysis_df"
        #     )

        #     if df_price is not None:

        #         df_price.columns = [

        #             c[0]
        #             if isinstance(c, tuple)
        #             else c

        #             for c in df_price.columns
        #         ]

        #         df_price.columns = [

        #             str(c).upper()

        #             for c in df_price.columns
        #         ]

        #     # ==========================================================
        #     # MAIN ENGINE
        #     # ==========================================================

        #     if (
        #         df_price is not None
        #         and len(df_price) > 50
        #     ):

        #         close = df_price["CLOSE"]

        #         high = df_price["HIGH"]

        #         low = df_price["LOW"]

        #         volume = df_price["VOLUME"]

        #         ma20 = close.rolling(20).mean()

        #         ma50 = close.rolling(50).mean()

        #         last_price = float(
        #             close.iloc[-1]
        #         )

        #         # ======================================================
        #         # STRUCTURE
        #         # ======================================================

        #         hh = (
        #             high.iloc[-1]
        #             >= high.tail(20).max() * 0.98
        #         )

        #         hl = (
        #             low.iloc[-1]
        #             > low.tail(20).min()
        #         )

        #         # ======================================================
        #         # MOMENTUM
        #         # ======================================================

        #         momentum = (
        #             (
        #                 last_price
        #                 - close.iloc[-10]
        #             )
        #             / max(close.iloc[-10], 1)
        #         )

        #         # ======================================================
        #         # VOLUME
        #         # ======================================================

        #         vol_ratio = (
        #             volume.iloc[-1]
        #             / max(
        #                 volume.tail(20).mean(),
        #                 1
        #             )
        #         )

        #         # ======================================================
        #         # ATR
        #         # ======================================================

        #         atr_pct = (
        #             (
        #                 high.tail(14).max()
        #                 - low.tail(14).min()
        #             )
        #             / max(last_price, 1)
        #         ) * 100

        #         # ======================================================
        #         # TREND MODE
        #         # ======================================================

        #         if (

        #             last_price > ma50.iloc[-1]
        #             and momentum > 0.07

        #         ):

        #             trend_mode = "strong_up"

        #         elif (

        #             momentum > 0.20
        #             and vol_ratio > 2
        #             and last_price > ma20.iloc[-1]

        #         ):

        #             trend_mode = "speculative"

        #         elif last_price > ma50.iloc[-1]:

        #             trend_mode = "up"

        #         elif last_price < ma50.iloc[-1]:

        #             trend_mode = "down"

        #         # ======================================================
        #         # VOLATILITY ADAPTIVE WINDOW
        #         # ======================================================

        #         if atr_pct >= 20:

        #             window_expand = 5

        #         elif atr_pct >= 10:

        #             window_expand = 3

        #         else:

        #             window_expand = 1

        #         # ======================================================
        #         # EXPAND WINDOW
        #         # ======================================================

        #         for name in [

        #             "near_low_start",
        #             "near_low_end",
        #             "next_low_start",
        #             "next_low_end",
        #             "near_high_start",
        #             "near_high_end",
        #             "next_high_start",
        #             "next_high_end",

        #         ]:

        #             value = locals().get(name)

        #             if value:

        #                 if "start" in name:

        #                     locals()[name] = (
        #                         value
        #                         - timedelta(
        #                             days=window_expand
        #                         )
        #                     )

        #                 else:

        #                     locals()[name] = (
        #                         value
        #                         + timedelta(
        #                             days=window_expand
        #                         )
        #                     )

        #         # ======================================================
        #         # VENUS SYNODIC
        #         # ======================================================

        #         venus_alignment = cycle.get(
        #             "venus_alignment",
        #             False
        #         )

        #         if venus_alignment:

        #             cycle_confidence += 15

        #         # ======================================================
        #         # SUN JUPITER
        #         # ======================================================

        #         sun_jupiter_alignment = cycle.get(
        #             "sun_jupiter_alignment",
        #             False
        #         )

        #         if sun_jupiter_alignment:

        #             if trend_mode in [
        #                 "strong_up",
        #                 "up"
        #             ]:

        #                 cycle_confidence += 15

        #             else:

        #                 cycle_confidence += 5

        #         # ======================================================
        #         # TIME GEOMETRY
        #         # ======================================================

        #         geometry_score = cycle.get(
        #             "geometry_score",
        #             0
        #         )

        #         cycle_confidence += geometry_score

        #         # ======================================================
        #         # TREND QUALITY
        #         # ======================================================

        #         if trend_mode == "up":

        #             cycle_confidence += 15

        #         elif trend_mode == "strong_up":

        #             cycle_confidence += 5

        #         elif trend_mode == "sideways":

        #             cycle_confidence += 15

        #         elif trend_mode == "down":

        #             cycle_confidence -= 10

        #         # ======================================================
        #         # MOMENTUM QUALITY
        #         # ======================================================

        #         if 0.03 <= momentum <= 0.15:

        #             cycle_confidence += 10

        #         elif momentum > 0.20:

        #             cycle_confidence -= 12

        #         # ======================================================
        #         # VOLATILITY QUALITY
        #         # ======================================================

        #         if 8 <= atr_pct <= 20:

        #             cycle_confidence += 15

        #         elif atr_pct > 30:

        #             cycle_confidence -= 10

        #         # ======================================================
        #         # STRUCTURE QUALITY
        #         # ======================================================

        #         if hh and hl:

        #             cycle_confidence += 10

        #         # ======================================================
        #         # CLEAN VOLUME
        #         # ======================================================

        #         if 1.2 <= vol_ratio <= 2.5:

        #             cycle_confidence += 5

        #         # ======================================================
        #         # MA20 POSITION
        #         # ======================================================

        #         distance_ma20 = (
        #             (
        #                 last_price
        #                 - ma20.iloc[-1]
        #             )
        #             / max(ma20.iloc[-1], 1)
        #         ) * 100

        #         if abs(distance_ma20) <= 3:

        #             cycle_confidence += 10

        #         elif distance_ma20 >= 10:

        #             cycle_confidence -= 10

        #         # ======================================================
        #         # CYCLE POSITION BONUS
        #         # ======================================================

        #         days_to_low = days_to(near_low_start)

        #         if (
        #             days_to_low is not None
        #             and 0 <= days_to_low <= 10
        #         ):
        #             cycle_confidence += 20

        #         if in_range(
        #             near_high_start,
        #             near_high_end
        #         ):

        #             cycle_confidence -= 10

        #         # ======================================================
        #         # NORMALIZE
        #         # ======================================================

        #         cycle_confidence = int(

        #             max(
        #                 0,
        #                 min(
        #                     cycle_confidence,
        #                     100
        #                 )
        #             )
        #         )

        #     # ==========================================================
        #     # METRICS
        #     # ==========================================================

        #     c1, c2 = st.columns(2)

        #     c1.metric(
        #         "Trend Mode",
        #         trend_mode
        #         .replace("_", " ")
        #         .title()
        #     )

        #     c2.metric(
        #         "Volatility",
        #         f"{atr_pct:.1f}%"
        #     )

        #     # ==========================================================
        #     # CURRENT POSITION
        #     # ==========================================================

        #     if in_range(
        #         near_low_start,
        #         near_low_end
        #     ):

        #         if cycle_confidence >= 80:

        #             st.success(
        #                 "🟢 High Probability Cycle Low"
        #             )

        #         elif cycle_confidence >= 65:

        #             st.info(
        #                 "⚖️ Medium Confidence Cycle Low"
        #             )

        #         else:

        #             st.warning(
        #                 "⚠️ Weak Cycle Low Alignment"
        #             )

        #     elif in_range(
        #         near_high_start,
        #         near_high_end
        #     ):

        #         if trend_mode in [
        #             "strong_up",
        #             "speculative"
        #         ]:

        #             st.info(
        #                 "📈 Trend Continuation Zone"
        #             )

        #         else:

        #             st.warning(
        #                 "🔴 Near Cycle High"
        #             )

        #     else:

        #         events = [

        #             (
        #                 "Cycle Low",
        #                 near_low_start
        #             ),

        #             (
        #                 "Cycle High",
        #                 near_high_start
        #             ),

        #             (
        #                 "Next Cycle Low",
        #                 next_low_start
        #             ),

        #             (
        #                 "Next Cycle High",
        #                 next_high_start
        #             ),
        #         ]

        #         future_events = [

        #             (n, d)

        #             for n, d in events

        #             if d and d >= today
        #         ]

        #         if future_events:

        #             name, date_event = min(

        #                 future_events,

        #                 key=lambda x: (
        #                     x[1] - today
        #                 ).days
        #             )

        #             d = days_to(date_event)

        #             if "Low" in name:

        #                 st.info(
        #                     f"⏳ {name} ({d} hari lagi)"
        #                 )

        #             else:

        #                 st.info(
        #                     f"📈 {name} ({d} hari lagi)"
        #                 )

        #         else:

        #             st.caption(
        #                 "⚖️ Tidak ada event cycle ke depan"
        #             )

        #     # ==========================================================
        #     # LOW WINDOW TABLE
        #     # ==========================================================

        #     st.markdown(
        #         "### 📉 Cycle Low Window"
        #     )

        #     low_df = pd.DataFrame({

        #         "Parameter": [

        #             "Last Major Low",

        #             "Near Cycle Low",

        #             "Next Cycle Low",
        #         ],

        #         "Value": [

        #             fmt(last_low),

        #             fmt_range(
        #                 near_low_start,
        #                 near_low_end
        #             ),

        #             fmt_range(
        #                 next_low_start,
        #                 next_low_end
        #             ),
        #         ],
        #     })

        #     st.table(
        #         low_df.set_index(
        #             "Parameter"
        #         )
        #     )

        #     # ==========================================================
        #     # HIGH WINDOW TABLE
        #     # ==========================================================

        #     st.markdown(
        #         "### 📈 Cycle High Window"
        #     )

        #     high_df = pd.DataFrame({

        #         "Parameter": [

        #             "Near High Window",

        #             "Next High Window",
        #         ],

        #         "Value": [

        #             fmt_range(
        #                 near_high_start,
        #                 near_high_end
        #             ),

        #             fmt_range(
        #                 next_high_start,
        #                 next_high_end
        #             ),
        #         ],
        #     })

        #     st.table(
        #         high_df.set_index(
        #             "Parameter"
        #         )
        #     )

    # ================= NEWS =================
    st.subheader("📰 News & Sentiment")

    import matplotlib.pyplot as plt
    import pandas as pd
    from app.utils.sentiment_analysis import (
        predict_lstm, generate_recommendation,
        WORDCLOUD_OK,
    )

    # ======================================================
    # LABEL SENTIMEN BASIC
    # ======================================================
    sent = news_result.get("sentiment")
    if sent == "NO_RECENT_NEWS":
        st.info(news_result.get("message", "Tidak ada berita terbaru"))
    elif sent == "POSITIVE":
        st.success("🟢 Sentimen Positif")
    elif sent == "NEGATIVE":
        st.warning("🟠 Sentimen Negatif")
    elif sent == "SPECULATIVE":
        st.error("🎢 Speculative / High Risk")
    else:
        st.info("⚪ Netral")

    # ======================================================
    # BERITA TERBARU (5 link)
    # ======================================================
    if news_result.get("news_count", 0) > 0:
        for n in news_result.get("news", [])[:5]:
            title = n.get("title", "-")
            link  = n.get("link", "#")
            age   = n.get("age_days")
            suffix = f" • {age} hari lalu" if age is not None else ""
            st.markdown(f"- [{title}]({link}){suffix}")

    # ======================================================
    # GOOGLE NEWS — ANALISIS LENGKAP
    # ======================================================
    sent_data = st.session_state.get(f"sent_result_{kode}")

    if not sent_data:
        if st.button("📰 Muat Sentimen & Analisis Berita", key=f"load_sent_{kode}"):
            from datetime import datetime, timedelta
            from app.utils.sentiment_analysis import smart_keyword, get_news
            _, _, kw_encoded = smart_keyword("", kode)
            sent_start = (datetime.now() - timedelta(days=30)).date()
            sent_end   = datetime.now().date()
            with st.spinner("Mengambil berita dari Google News..."):
                gn_result = get_news(kw_encoded, sent_start, sent_end)
            st.session_state[f"sent_result_{kode}"] = gn_result
            st.rerun()

    if sent_data:
        df_gn, df_daily, wc, common, media = sent_data

        if df_gn is None or df_gn.empty:
            st.info("Tidak ada berita Google News ditemukan untuk 30 hari terakhir.")
        else:
            st.divider()
            st.markdown("### 📊 Analisis Sentimen Google News (30 Hari)")

            # -- distribusi sentimen --
            st.markdown("**Distribusi Sentimen**")
            st.bar_chart(df_gn["sentiment_label"].value_counts())

            # -- wordcloud & top kata --
            col_wc, col_top = st.columns(2)
            with col_wc:
                st.markdown("**☁️ WordCloud Berita**")
                if wc and WORDCLOUD_OK:
                    fig, ax = plt.subplots()
                    ax.imshow(wc)
                    ax.axis("off")
                    st.pyplot(fig)
                else:
                    st.caption("Install `wordcloud` untuk mengaktifkan fitur ini.")

            with col_top:
                st.markdown("**📊 Top 10 Kata**")
                if common:
                    st.table(pd.DataFrame(common, columns=["Kata", "Jumlah"]))

            # -- top media --
            if media is not None and not media.empty:
                st.markdown("**🏆 Media yang Memberitakan**")
                st.bar_chart(media)

            # -- korelasi sentimen vs harga --
            if df_daily is not None:
                df_price_copy = df_price.copy().reset_index()
                df_price_copy.columns = [str(c).upper() for c in df_price_copy.columns]
                price_col = next((c for c in df_price_copy.columns if "CLOSE" in c), None)

                if price_col:
                    if "DATE" in df_price_copy.columns:
                        df_price_copy["Date"] = pd.to_datetime(df_price_copy["DATE"]).dt.date
                    else:
                        df_price_copy["Date"] = pd.to_datetime(df_price_copy.index).date

                    df_price_copy["Pct_Change (%)"] = df_price_copy[price_col].pct_change() * 100
                    df_daily["Date"] = pd.to_datetime(df_daily["Date"]).dt.date

                    df_corr = pd.merge(
                        df_price_copy[["Date", "Pct_Change (%)"]],
                        df_daily[["Date", "sentiment_score"]],
                        on="Date", how="inner"
                    ).dropna()

                    if len(df_corr) > 2:
                        corr = df_corr["Pct_Change (%)"].corr(df_corr["sentiment_score"])
                        st.markdown("**📊 Korelasi Sentimen vs Perubahan Harga**")
                        st.metric("Nilai Korelasi (Pearson)", f"{corr:.4f}")

                        if corr > 0.3:
                            st.success("📈 Korelasi Positif — sentimen sejalan dengan kenaikan harga")
                        elif corr < -0.3:
                            st.error("📉 Korelasi Negatif — sentimen berlawanan arah dengan harga")
                        else:
                            st.warning("⚖️ Korelasi Lemah — sentimen kurang berpengaruh pada harga")

                        fig, ax = plt.subplots(figsize=(6, 3))
                        ax.scatter(df_corr["sentiment_score"], df_corr["Pct_Change (%)"], alpha=0.7)
                        ax.axhline(0, color="gray", linewidth=0.5)
                        ax.axvline(0, color="gray", linewidth=0.5)
                        ax.set_xlabel("Sentiment Score")
                        ax.set_ylabel("Perubahan Harga (%)")
                        plt.tight_layout()
                        st.pyplot(fig)

                        # -- rekomendasi --
                        rec_today, rec_tomorrow = generate_recommendation(df_corr)
                        col_a, col_b = st.columns(2)
                        for col_r, label, rec in [
                            (col_a, "📅 Hari Ini", rec_today),
                            (col_b, "📅 Besok (Estimasi)", rec_tomorrow),
                        ]:
                            with col_r:
                                if rec == "BELI":
                                    st.success(f"**{label}:** ✅ {rec}")
                                elif rec == "JANGAN BELI":
                                    st.error(f"**{label}:** ❌ {rec}")
                                else:
                                    st.warning(f"**{label}:** 👀 {rec}")

            # -- prediksi harga (mlp) --
            st.markdown("**🤖 Prediksi Harga (Neural Network)**")
            df_price_lstm = df_price.copy()
            df_price_lstm.columns = [str(c).upper() for c in df_price_lstm.columns]
            pc = next((c for c in df_price_lstm.columns if "CLOSE" in c), None)
            if pc:
                df_price_lstm = df_price_lstm.rename(columns={pc: "Close"})
                with st.spinner("Melatih model prediksi..."):
                    df_pred, err = predict_lstm(df_price_lstm)
                if err:
                    st.warning(err)
                elif df_pred is not None:
                    fig, ax = plt.subplots(figsize=(10, 3))
                    ax.plot(df_pred.index, df_pred["Close"],    label="Actual",   linewidth=2)
                    ax.plot(df_pred.index, df_pred["Prediksi"], label="Prediksi", linestyle="--")
                    ax.legend()
                    plt.tight_layout()
                    st.pyplot(fig)

            # -- daftar berita lengkap --
            with st.expander("📰 Lihat Semua Berita"):
                show_cols = [c for c in ["Date", "title", "media", "sentiment_label", "sentiment_score"]
                             if c in df_gn.columns]
                st.dataframe(df_gn[show_cols], use_container_width=True, hide_index=True)

    # ================= INSIGHT =================
    st.subheader("🧠 Insight")

    if "Bullish" in trend:
        st.success("⬆️ Buy on pullback")
    elif "Bearish" in trend:
        st.error("⬇️ Avoid / Wait")
    else:
        st.info("➡️ Sideways / Wait")

    # ================= TELEGRAM =================
    st.subheader("📤 Share Analysis")

    pwd = st.text_input("Password", type="password")

    try:
        _share_pwd = st.secrets.get("SHARE_PASSWORD") or os.getenv("SHARE_PASSWORD")
    except Exception:
        import os as _os
        _share_pwd = _os.getenv("SHARE_PASSWORD")

    if st.button("Send to Telegram") and pwd == _share_pwd:
        msg = render_stock_analysis_message(
            kode=kode,
            timeframe=timeframe,
            analysis=result,
            news_result=news_result,
            insight_text=trend,
            df_price=df_price,
        )
        send_message(msg)
        st.success("Terkirim ✅")