# ==========================================================
# FIX PYTHON PATH
# ==========================================================
import sys
import os
from datetime import date, datetime, timedelta
import pytz

tz = pytz.timezone("Asia/Jakarta")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# ==========================================================
# LOAD ENV (WAJIB)
# ==========================================================
from dotenv import load_dotenv
load_dotenv()

# ==========================================================
# IMPORTS
# ==========================================================
import streamlit as st

# streamlit_cookies_manager still uses the removed `st.cache` API internally
st.cache = st.cache_data

import pandas as pd
import numpy as np


from app.core.engine import ScreenerEngine
from app.core.scanner_bsjp import scan_bsjp
from app.config.saham_list import SAHAM_LIST
from app.config.saham_profile import SAHAM_PROFILE
from app.config.dividend_list import DIVIDEND_LIST
from app.renderers.telegram import render_telegram
from app.services.telegram_bot import send_message
from app.services.logic import round_price
from app.services.logic import detect_day_trade, detect_market_mover
from app.services.data import get_price_data
from app.utils.news_engine import fetch_stock_news

from streamlit_cookies_manager import EncryptedCookieManager
from app.stock_analysis.ui import render_stock_analysis

from app.tracker.tracker import (
    load_trades,
    save_buy,
    save_sell,
    enrich_trades,
    delete_trade,
    load_dividends,
    save_dividend,
    save_dividends,
    delete_dividends_by_trade,
)

from app.renderers.telegram_stock_analysis import render_stock_analysis_message
from app.core.dividend_engine import DividendEngine
from app.screeners.multi_algo import scan_multi_algo, DEFAULT_CONFIG
from app.utils.sentiment_analysis import (
    smart_keyword, get_yahoo, get_full_history, get_alpha,
    get_news, predict_lstm, generate_recommendation,
    TENSORFLOW_OK, WORDCLOUD_OK, SASTRAWI_OK, ALPHA_OK,
)

# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="Cuanmology Kebun - Stock Screener Dashboard",
    page_icon="assets/logo-thumb.png",
    layout="wide"
)

# ==========================================================
# LOGIN CONFIG
# ==========================================================

try:
    APP_PASSWORD = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD"))
except Exception:
    APP_PASSWORD = os.getenv("APP_PASSWORD")

# ==========================================================
# COOKIE MANAGER
# ==========================================================

cookies = EncryptedCookieManager(

    prefix="cuanmology_",

    password="cuanmology-super-secret-cookie-key"

)

if not cookies.ready():

    st.stop()

# ==========================================================
# SESSION INIT
# ==========================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False

if "username" not in st.session_state:

    st.session_state.username = ""

# ==========================================================
# AUTO LOGIN FROM COOKIE
# ==========================================================

saved_login = cookies.get("logged_in")

saved_username = cookies.get("username")

saved_expiry = cookies.get("expiry")

if (
    saved_login == "true"
    and saved_username
    and saved_expiry
):

    try:

        expiry_date = datetime.fromisoformat(
            saved_expiry
        )

        # ======================
        # STILL VALID
        # ======================

        if datetime.now() < expiry_date:

            st.session_state.logged_in = True

            st.session_state.username = (
                saved_username
            )

        # ======================
        # EXPIRED
        # ======================

        else:

            cookies["logged_in"] = ""

            cookies["username"] = ""

            cookies["expiry"] = ""

            cookies.save()

    except:

        pass

# ==========================================================
# LOGIN PAGE
# ==========================================================

if not st.session_state.logged_in:

    left, center, right = st.columns([1.5, 2, 1.5])

    with center:

        st.image("assets/logo-login.png", width=600)

        st.caption(
            "🔐 Private dashboard access"
        )

        username = st.text_input(
            "Nama",
            max_chars=25
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button(
            "Login",
            use_container_width=True
        ):

            if password == APP_PASSWORD:

                # ======================
                # SESSION
                # ======================

                st.session_state.logged_in = True

                st.session_state.username = username

                # ======================
                # SAVE COOKIE
                # ======================

                expiry_date = (
                    datetime.now()
                    + timedelta(days=6)
                )

                cookies["logged_in"] = "true"

                cookies["username"] = username

                cookies["expiry"] = (
                    expiry_date.isoformat()
                )

                cookies.save()

                st.rerun()

            else:

                st.error(
                    "❌ Password salah"
                )

    st.stop()

# ==========================================================
# HEADER
# ==========================================================

st.title(
    "🤖 Stock Screener Dashboard (Beta)"
)

st.caption(
    "Multi-strategy stock screening"
)


# ==========================================================
# SIDEBAR USER MENU
# ==========================================================

with st.sidebar:

    username = st.session_state.username

    short_name = (
        username[:25]
        if username
        else "US"
    )

    with st.popover(
        f"👤 {short_name}"
    ):

        st.markdown(
            f"### {username}"
        )

        st.caption(
            "Cuanmology kebun Screener Dashboard"
        )

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):

            # ======================
            # CLEAR SESSION
            # ======================

            st.session_state.logged_in = False

            st.session_state.username = ""

            # ======================
            # CLEAR COOKIE
            # ======================

            cookies["logged_in"] = ""

            cookies["username"] = ""

            cookies.save()

            st.rerun()

# ==========================================================
# ======================= HELPERS ==========================
# ==========================================================

def format_price(x):
    return f"Rp {int(float(x)):,}".replace(",", ".")


def format_range(a, b):
    return f"{format_price(a)} – {format_price(b)}"


def format_tp(tp):
    return " / ".join(format_price(x) for x in tp)


def price_position(last_price, entry_low, entry_high):
    if entry_low <= last_price <= entry_high:
        return "INSIDE"
    elif last_price < entry_low:
        return "BELOW"
    return "ABOVE"

def format_date_indo(d):
    if not d or pd.isna(d):
        return "-"
    return pd.to_datetime(d).strftime("%d-%b-%Y")

def near_resistance(last_price, resistance, threshold_pct=4):
    return 0 <= (resistance - last_price) / resistance * 100 <= threshold_pct


def near_entry(last_price, entry_high, threshold_pct=1):
    return 0 <= (last_price - entry_high) / entry_high * 100 <= threshold_pct


def score_color(val):
    if val >= 85:
        return "background-color:#16a34a;color:white"
    elif val >= 70:
        return "background-color:#22c55e;color:black"
    elif val >= 60:
        return "background-color:#fde047;color:black"
    return "background-color:#f87171;color:white"


def render_df(data):
    df = pd.DataFrame(data)
    if df.empty:
        st.info("Tidak ada data")
        return
    if "Score" in df.columns:
        df = df.style.map(score_color, subset=["Score"])
    st.dataframe(df, use_container_width=True)

def require_trading_password():
    try:
        SHARE_PASSWORD = st.secrets.get("SHARE_PASSWORD") or os.getenv("SHARE_PASSWORD")
    except Exception:
        SHARE_PASSWORD = os.getenv("SHARE_PASSWORD")

    # kalau belum pernah login
    if "trading_auth_time" not in st.session_state:
        st.session_state.trading_auth_time = None

    # cek apakah masih dalam 7 hari
    if st.session_state.trading_auth_time:
        if datetime.now() - st.session_state.trading_auth_time < timedelta(days=7):
            return True  # masih valid

    # ===== FORM PASSWORD =====
    st.warning("🔒 Halaman ini dilindungi password")

    password_input = st.text_input("Masukkan password", type="password")

    if st.button("Login"):
        if password_input == SHARE_PASSWORD:
            st.session_state.trading_auth_time = datetime.now()
            st.success("✅ Login berhasil")
            st.rerun()
        else:
            st.error("❌ Password salah")

    return False

def calc_minor_support(df, lookback=12):
    """
    Minor support = lowest low dari N candle terakhir
    Aman untuk:
    - low / Low
    - MultiIndex
    - memastikan return SELALU float atau None
    """
    if df is None or df.empty:
        return None

    recent = df.tail(lookback)

    # === CASE 1: kolom tunggal ===
    for col in ["low", "Low", "LOW"]:
        if col in recent.columns:
            series = recent[col].dropna()
            if series.empty:
                return None
            return float(series.min())

    # === CASE 2: MultiIndex ===
    if isinstance(recent.columns, pd.MultiIndex):
        for col in recent.columns:
            if str(col[-1]).lower() == "low":
                series = recent[col].dropna()
                if series.empty:
                    return None
                return float(series.min())

    return None

# =============================
# CACHE
# =============================

import os
import pandas as pd

from datetime import datetime

CACHE_FILE = (
    "data/dividend_cache.parquet"
)

# =============================
# CHECK CACHE
# =============================

def is_cache_today(path):

    if not os.path.exists(path):

        return False

    modified_date = datetime.fromtimestamp(
        os.path.getmtime(path)
    ).date()

    return (
        modified_date
        == datetime.now().date()
    )

# =============================
# LOAD DIVIDEND DATA
# =============================

@st.cache_data(ttl=3600)

def load_dividend_data(symbols):

    # ======================
    # USE CACHE
    # ======================

    if is_cache_today(CACHE_FILE):

        return pd.read_parquet(
            CACHE_FILE
        )

    # ======================
    # RE-SCAN
    # ======================

    df = DividendEngine.scan(symbols)

    # ======================
    # SAVE CACHE
    # ======================

    os.makedirs(
        "data",
        exist_ok=True
    )

    df.to_parquet(
        CACHE_FILE
    )

    return df


def render_dividend_screener():
    st.header("💰 Dividend Screener")
    st.caption("Daftar saham dividen dipisah per sektor")

    symbols = [s + ".JK" for s in DIVIDEND_LIST]

    with st.spinner("Loading dividend database..."):
        df = load_dividend_data(symbols)

    if df.empty:
        st.warning("Tidak ada data ditemukan")
        return

    # =============================
    # FIX PAYOUT %
    # =============================
    def normalize_payout(x):
        if not x:
            return 0
        if x < 2:
            return x * 100
        return x

    df["payout_ratio"] = df["payout_ratio"].apply(normalize_payout)

    # =============================
    # FORMAT DATA NUMERIC
    # =============================
    df["last_dividend_1"] = df["last_dividend_1"].round(2)
    df["last_dividend_2"] = df["last_dividend_2"].round(2)
    df["price"] = df["price"].fillna(0)

    # Base dividend terbesar
    df["dividend_base"] = df[["last_dividend_1", "last_dividend_2"]].max(axis=1)

    # =============================
    # EXCLUDE YANG TIDAK ADA DIVIDEN
    # =============================
    df = df[
        (df["dividend_base"] > 0) &
        (df["price"] > 0)
    ].copy()

    # =============================
    # SIMPAN DATETIME RAW UNTUK FILTER
    # =============================
    import pandas as pd
    from datetime import datetime, timedelta

    df["dt1"] = pd.to_datetime(df["last_dividend_date_1"], errors="coerce")
    df["dt2"] = pd.to_datetime(df["last_dividend_date_2"], errors="coerce")

    # =============================
    # FILTER BULAN / TAHUN / UPCOMING
    # =============================
    st.subheader("🔎 Filter")

    colf1, colf2, colf3 = st.columns(3)

    # Bulan
    bulan_list = {
        "All": 0,
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "Mei": 5, "Jun": 6,
        "Jul": 7, "Agu": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Des": 12
    }
    selected_month = colf1.selectbox("📅 Bulan Ex-Date", list(bulan_list.keys()))

    # Tahun
    years_available = sorted(
        set(df["dt1"].dropna().dt.year.tolist()) |
        set(df["dt2"].dropna().dt.year.tolist())
    )
    years_available = ["All"] + [str(y) for y in years_available]
    selected_year = colf2.selectbox("🗓️ Tahun", years_available)

    # Apply filter bulan
    if selected_month != "All":
        m = bulan_list[selected_month]
        df = df[
            (df["dt1"].dt.month == m) |
            (df["dt2"].dt.month == m)
        ]

    # Apply filter tahun
    if selected_year != "All":
        y = int(selected_year)
        df = df[
            (df["dt1"].dt.year == y) |
            (df["dt2"].dt.year == y)
        ]

    if df.empty:
        st.warning("Tidak ada data sesuai filter.")
        return

    # =============================
    # FORMAT TANGGAL (DISPLAY)
    # =============================
    bulan_map = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "Mei", "06": "Jun", "07": "Jul", "08": "Agu",
        "09": "Sep", "10": "Okt", "11": "Nov", "12": "Des"
    }

    def format_tanggal(tgl):
        if pd.isna(tgl):
            return "-"
        tgl = str(pd.to_datetime(tgl).date())
        y, m, d = tgl.split("-")
        return f"{int(d)}-{bulan_map[m]}-{y}"

    df["last_dividend_date_1"] = df["dt1"].apply(format_tanggal)
    df["last_dividend_date_2"] = df["dt2"].apply(format_tanggal)

    # Hilangin .JK
    df["symbol"] = df["symbol"].str.replace(".JK", "", regex=False)

    # =============================
    # SORT GLOBAL (BASE DIVIDEND)
    # =============================
    df = df.sort_values("dividend_base", ascending=False).reset_index(drop=True)

    # =============================
    # CLASS 1: SIZE
    # =============================
    total = len(df)

    def classify_dividend(idx):
        pct = idx / total
        if pct <= 0.2:
            return "💰 Big"
        elif pct <= 0.4:
            return "🟢 High"
        elif pct <= 0.6:
            return "🟡 Medium"
        elif pct <= 0.8:
            return "🔵 Low"
        else:
            return "🌱 Tiny"

    df["Class"] = [classify_dividend(i) for i in range(total)]

    class_order = {
        "💰 Big": 1,
        "🟢 High": 2,
        "🟡 Medium": 3,
        "🔵 Low": 4,
        "🌱 Tiny": 5
    }
    df["class_rank"] = df["Class"].map(class_order)

    # =============================
    # CLASS 2: TYPE
    # =============================
    cyclical_sectors = ["Energy", "Basic Materials"]

    def classify_type(row):
        years = row["years_paying"]
        payout = row["payout_ratio"]
        sector = row["sector"]

        if payout > 100:
            return "🔴 Risky"
        elif sector in cyclical_sectors:
            return "🔁 Cyclical"
        elif years >= 10:
            return "🏦 Stable"
        elif years >= 3:
            return "🌱 Growing"
        else:
            return "⚪ New"

    df["Type"] = df.apply(classify_type, axis=1)

    # =============================
    # FORMAT PRICE
    # =============================
    def format_rupiah(x):
        try:
            return f"Rp {int(x):,}".replace(",", ".")
        except:
            return "-"

    df["Harga"] = df["price"].apply(format_rupiah)

    # =============================
    # RENAME
    # =============================
    df = df.rename(columns={
        "symbol": "Ticker",
        "years_paying": "Years Paying",
        "last_dividend_1": "Last Div 1",
        "last_dividend_2": "Last Div 2",
        "last_dividend_date_1": "Date 1",
        "last_dividend_date_2": "Date 2",
        "payout_ratio": "Payout Ratio (%)"
    })

    # =============================
    # METRICS
    # =============================
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Stocks", len(df))
    col2.metric("Highest Dividend", f"{df['dividend_base'].max():,.0f}")
    col3.metric("Avg Dividend", f"{df['dividend_base'].mean():,.0f}")

    st.divider()

    # =============================
    # COLOR PAYOUT
    # =============================
    def color_payout(val):
        try:
            val = float(val)
        except:
            return ""
        if val <= 50:
            return "background-color:#d4edda;color:#155724;"
        elif val <= 80:
            return "background-color:#fff3cd;color:#856404;"
        elif val <= 100:
            return "background-color:#ffe5b4;color:#8a4b00;"
        else:
            return "background-color:#f8d7da;color:#721c24;"

    # =============================
    # LOOP PER SECTOR
    # =============================
    sectors = sorted(df["sector"].dropna().unique())

    for sector in sectors:
        sector_df = df[df["sector"] == sector].copy()

        sector_df = sector_df.sort_values(
            by=["class_rank", "price"],
            ascending=[True, False]
        ).reset_index(drop=True)

        sector_df.insert(0, "Rank", range(1, len(sector_df) + 1))

        sector_df = sector_df[
            [
                "Rank",
                "Ticker",
                "Harga",
                "Class",
                "Type",
                "Last Div 1",
                "Last Div 2",
                "Years Paying",
                "Payout Ratio (%)",
                "Date 1",
                "Date 2"
            ]
        ]

        sector_icons = {
            "Financial Services": "🏦",
            "Energy": "🛢️",
            "Consumer Defensive": "🛒",
            "Consumer Cyclical": "🛍️",
            "Industrials": "🏭",
            "Basic Materials": "🧱",
            "Healthcare": "💊",
            "Technology": "💻",
            "Communication Services": "📡",
            "Utilities": "⚡",
            "Real Estate": "🏢"
        }

        icon = sector_icons.get(sector, "📊")

        st.subheader(f"{icon} {sector} ({len(sector_df)})")

        styled_df = (
            sector_df.style
            .map(color_payout, subset=["Payout Ratio (%)"])
            .format({
                "Last Div 1": "{:,.2f}",
                "Last Div 2": "{:,.2f}",
                "Payout Ratio (%)": "{:,.2f}"
            })
        )

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

# ==========================================================
# ===================== IMPORT ==============================
# ==========================================================
import os
import streamlit as st
import pandas as pd
import requests
from datetime import datetime

from app.config.saham_list import SAHAM_LIST
from app.core.scanner import scan_day
from app.core.engine import ScreenerEngine

# 🔥 FIX YFINANCE ERROR
os.environ["YFINANCE_NO_SQLITE"] = "1"


# ==========================================================
# ===================== TELEGRAM ============================
# ==========================================================

def send_telegram(msg):

    try:
        bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
    except Exception:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass


# ==========================================================
# ===================== HELPERS =============================
# ==========================================================

import pandas as pd

def format_rsi_status(status):

    if not status:
        return "⚪ Normal"

    if "Oversold" in status:
        return "🟢 Oversold"

    elif "Overbought" in status:
        return "🔴 Overbought"

    else:
        return "⚪ Normal"


# ==========================================================
# ===================== WEEK ================================
# ==========================================================

def scan_week(min_price=None, max_price=None):

    engine = ScreenerEngine()

    results = engine.run(
        SAHAM_LIST[:1000],
        "swing_trade_week"
    )

    entry_rows = []
    watchlist_rows = []

    for r in results:

        if r is None:
            continue

        try:

            # ==================================================
            # BASIC DATA
            # ==================================================

            last_price = float(r.last_price)

            entry_low = float(r.entry_low)

            entry_high = float(r.entry_high)

            score = int(r.score)

            setup = str(r.setup)

            trend = str(r.trend)

            # ==================================================
            # DISTANCE
            # ==================================================

            distance = abs(
                last_price - entry_low
            ) / max(entry_low, 1)

            # ==================================================
            # ENTRY CHECK
            # ==================================================

            distance_entry = (

                abs(last_price - entry_low)

                / max(entry_low, 1)
            )

            # ==================================================
            # TRUE ENTRY ZONE
            # ==================================================

            in_entry = (

                entry_low <= last_price <= entry_high
            )

            # ==================================================
            # NEAR ENTRY
            # ==================================================

            near_entry = (

                distance_entry <= 0.03
            )

            # ==================================================
            # EXTENDED FILTER
            # ==================================================

            too_extended = (

                distance >= 0.06
            )

            # ==================================================
            # READY ENTRY
            # ==================================================

            ready_entry = (

                near_entry

                and

                not too_extended

                and

                trend != "Extended"

                and

                setup in [

                    "🔥 Elite Rebound",

                    "🚀 Strong Pullback",

                    "⚡ Healthy Setup"
                ]
            )

            # ==================================================
            # STATUS
            # ==================================================

            if score >= 90:

                status = "🔥 Top Momentum"

            elif score >= 80:

                status = "🚀 Strong Momentum"

            elif score >= 70:

                status = "⚡ Pre-Breakout"

            elif score >= 60:

                status = "📈 Trend"

            else:

                status = "👀 Watchlist"

            # ==================================================
            # VOLUME
            # ==================================================

            volume_display = "-"

            try:

                volume_display = (
                    r.score_breakdown.get(
                        "Volume",
                        "-"
                    )
                )

            except:
                pass

            # ==================================================
            # ROW
            # ==================================================

            row = {

                "Kode": r.kode,

                "Harga": int(last_price),

                "Score": score,

                "Setup": (

                    setup

                    if ready_entry

                    else "👀 Watchlist"
                ),

                "Trend": trend,

                "Near Entry": near_entry,

                "Distance": round(distance, 3),

                "Volume": volume_display,

                "Entry": (
                    f"{int(entry_low)}"
                    f" - "
                    f"{int(entry_high)}"
                ),

                "TP": (
                    f"{int(r.tp[0])}"
                    f" / "
                    f"{int(r.tp[1])}"
                ),

                "SL": int(r.sl),
            }

            # ==================================================
            # SPLIT ENTRY & WATCHLIST
            # ==================================================

            if ready_entry:

                entry_rows.append(row)

            else:

                watchlist_rows.append(row)

        except Exception as e:

            print(
                "[ERROR]",
                getattr(r, "kode", "-"),
                e
            )

            continue

    # ======================================================
    # DATAFRAME
    # ======================================================

    entry_df = pd.DataFrame(entry_rows)

    watchlist_df = pd.DataFrame(watchlist_rows)

    # ======================================================
    # FILTER PRICE
    # ======================================================

    if (
        min_price is not None
        and
        max_price is not None
    ):

        if not entry_df.empty:

            entry_df = entry_df[

                (
                    entry_df["Harga"]
                    >=
                    min_price
                )

                &

                (
                    entry_df["Harga"]
                    <=
                    max_price
                )
            ]

        if not watchlist_df.empty:

            watchlist_df = watchlist_df[

                (
                    watchlist_df["Harga"]
                    >=
                    min_price
                )

                &

                (
                    watchlist_df["Harga"]
                    <=
                    max_price
                )
            ]

    # ======================================================
    # SORT ENTRY
    # ======================================================

    if not entry_df.empty:

        entry_df = entry_df.sort_values(

            by=[
                "Score",
                "Distance"
            ],

            ascending=[
                False,
                True
            ]
        )

        entry_df = entry_df.head(15)

        entry_df.reset_index(
            drop=True,
            inplace=True
        )

        entry_df.index += 1

    # ======================================================
    # SORT WATCHLIST
    # ======================================================

    if not watchlist_df.empty:

        watchlist_df = watchlist_df.sort_values(

            by=[
                "Score",
                "Distance"
            ],

            ascending=[
                False,
                True
            ]
        )

        watchlist_df = watchlist_df.head(15)

        watchlist_df.reset_index(
            drop=True,
            inplace=True
        )

        watchlist_df.index += 1

    # ======================================================
    # TERMINAL DEBUG
    # ======================================================

    print("\n" + "=" * 80)
    print("🚀 READY ENTRY")
    print("=" * 80)

    if not entry_df.empty:

        for _, row in entry_df.iterrows():

            print(
                f"✅ {row['Kode']} | "
                f"Score {row['Score']} | "
                f"{row['Trend']} | "
                f"Near {row['Near Entry']} | "
                f"Dist {row['Distance']}"
            )

    else:

        print("Tidak ada ready entry")

    print("\n" + "=" * 80)
    print("👀 WATCHLIST")
    print("=" * 80)

    if not watchlist_df.empty:

        for _, row in watchlist_df.iterrows():

            print(
                f"👀 {row['Kode']} | "
                f"Score {row['Score']} | "
                f"{row['Trend']} | "
                f"Near {row['Near Entry']} | "
                f"Dist {row['Distance']}"
            )

    else:

        print("Tidak ada watchlist")

    return entry_df, watchlist_df

# ==========================================================
# ===================== MARKET OVERVIEW =====================
# ==========================================================

# Indeks yang benar-benar tersedia via Yahoo Finance untuk BEI.
# IDX30 / IDX80 / ISSI / KOMPAS100 / BISNIS-27 TIDAK ada feed-nya di Yahoo Finance,
# jadi tidak dimasukkan (dibanding mengarang data).
_INDEX_OPTIONS = {
    "IHSG": {"symbol": "^JKSE",   "tag": "HEADLINE", "sub": "COMPOSITE"},
    "LQ45": {"symbol": "^JKLQ45", "tag": "HEADLINE", "sub": "LQ45"},
    "JII":  {"symbol": "^JKII",   "tag": "SYARIAH",  "sub": "JAKARTA ISLAMIC INDEX"},
}


@st.cache_data(ttl=900)
def _load_index_history(symbol):
    import yfinance as yf

    df = yf.download(symbol, period="2y", interval="1d", progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).upper().strip() for c in df.columns]

    return df.dropna()


@st.cache_data(ttl=120)
def _load_index_intraday(symbol):
    import yfinance as yf

    # Data harian di Yahoo untuk indeks IDX kadang telat 1 hari bursa,
    # tapi data intraday (5m) selalu mengikuti sesi terakhir yang sudah jalan.
    df = yf.download(symbol, period="5d", interval="5m", progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).upper().strip() for c in df.columns]

    return df.dropna()


def _resample_intraday_to_daily(intraday_df):
    """Agregasi bar intraday jadi OHLCV harian (termasuk sesi hari berjalan)."""

    if intraday_df is None or intraday_df.empty:
        return pd.DataFrame()

    df = intraday_df.copy()
    df["_date"] = df.index.date

    daily = df.groupby("_date").agg(
        OPEN=("OPEN", "first"),
        HIGH=("HIGH", "max"),
        LOW=("LOW", "min"),
        CLOSE=("CLOSE", "last"),
        VOLUME=("VOLUME", "sum"),
    )
    daily.index = pd.to_datetime(daily.index)

    return daily


def _augment_daily_with_intraday(daily_df, intraday_df):
    """Timpa/tambah bar hari terakhir di data harian dengan agregat intraday,
    supaya chart & statistik selalu mengikuti sesi terkini walau bar harian
    resmi dari Yahoo belum ter-update."""

    today_bar = _resample_intraday_to_daily(intraday_df)

    if today_bar.empty:
        return daily_df if daily_df is not None else pd.DataFrame()

    today_bar = today_bar.iloc[[-1]]

    if daily_df is None or daily_df.empty:
        return today_bar

    if daily_df.index[-1].date() == today_bar.index[-1].date():
        out = daily_df.copy()
        out.iloc[-1] = today_bar.iloc[-1]
        return out

    return pd.concat([daily_df, today_bar])


@st.cache_data(ttl=120)
def _load_market_movers_data():
    import yfinance as yf
    from app.config.hot_saham_list import HOT_SAHAM_LIST
    from app.utils.broker_flow import calc_flow_from_price

    tickers = [f"{code}.JK" for code in HOT_SAHAM_LIST]

    # Pakai data intraday 15 menit lalu di-resample harian sendiri, karena
    # bar harian bawaan Yahoo untuk saham IDX bisa telat 1 hari bursa
    # dibanding data intraday yang sudah mengikuti sesi terkini.
    raw = yf.download(
        tickers,
        period="10d",
        interval="15m",
        group_by="ticker",
        threads=True,
        progress=False,
    )

    rows = []

    for code, sym in zip(HOT_SAHAM_LIST, tickers):

        try:
            intraday = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            continue

        intraday = intraday.dropna(subset=["Close", "Volume"])

        if intraday.empty:
            continue

        intraday.columns = [str(c).upper().strip() for c in intraday.columns]
        daily = _resample_intraday_to_daily(intraday)

        if len(daily) < 2:
            continue

        last_close = daily["CLOSE"].iloc[-1]
        prev_close = daily["CLOSE"].iloc[-2]

        if not prev_close or last_close <= 0:
            continue

        chg_pct = (last_close / prev_close - 1) * 100
        volume = int(daily["VOLUME"].iloc[-1])

        if volume <= 0:
            continue

        net_asing_est = None
        df_flow = calc_flow_from_price(daily, days=len(daily))

        if df_flow is not None and not df_flow.empty:
            last_flow = df_flow.iloc[-1]
            net_asing_est = last_flow["asing_flow"] + last_flow["retail_flow"]

        rows.append({
            "Kode": code,
            "Tanggal": daily.index[-1].date(),
            "Close": last_close,
            "Perubahan (%)": round(chg_pct, 2),
            "Volume": volume,
            "Net Asing Estimasi (Rp)": round(net_asing_est) if net_asing_est is not None else 0,
        })

    return pd.DataFrame(rows)


def render_market_overview():
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if "mo_selected_index" not in st.session_state:
        st.session_state["mo_selected_index"] = "IHSG"

    # ---- muat data semua indeks: histori harian + intraday (3 simbol, di-cache) ----
    idx_daily = {}
    idx_intraday = {}
    idx_full = {}
    for name, meta in _INDEX_OPTIONS.items():
        try:
            idx_daily[name] = _load_index_history(meta["symbol"])
        except Exception:
            idx_daily[name] = pd.DataFrame()
        try:
            idx_intraday[name] = _load_index_intraday(meta["symbol"])
        except Exception:
            idx_intraday[name] = pd.DataFrame()
        idx_full[name] = _augment_daily_with_intraday(idx_daily[name], idx_intraday[name])

    col_side, col_main = st.columns([1, 3], gap="medium")

    # ======================================================
    # SIDEBAR — DAFTAR PERFORMA INDEKS
    # ======================================================
    with col_side:

        ihsg_full = idx_full.get("IHSG")
        _BULAN_SHORT = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                         "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        if ihsg_full is not None and not ihsg_full.empty:
            _d = ihsg_full.index.max()
            _upd = f"{_d.day:02d} {_BULAN_SHORT[_d.month]} {_d.year}"
        else:
            _upd = "-"

        st.markdown(
            f"""
            <div style="font-size:0.7rem; font-weight:700; letter-spacing:1px;
                        color:#6b7280; text-transform:uppercase;">Performa</div>
            <div style="font-size:0.7rem; color:#9ca3af; margin-bottom:8px;">
                🟢 data per : {_upd}
            </div>
            """,
            unsafe_allow_html=True,
        )

        for name, meta in _INDEX_OPTIONS.items():
            df = idx_full.get(name)

            if df is None or df.empty or len(df) < 2:
                continue

            last = df["CLOSE"].iloc[-1]
            prev = df["CLOSE"].iloc[-2]
            chg_pct = ((last / prev) - 1) * 100 if prev else 0
            up = chg_pct >= 0
            color = "#1b8a5a" if up else "#d64545"
            arrow = "▲" if up else "▼"
            is_selected = st.session_state["mo_selected_index"] == name

            st.markdown(
                f"""
                <div style="border-left:4px solid {color if is_selected else 'transparent'};
                            background:{'#eef6f0' if is_selected else 'transparent'};
                            border-radius:6px; padding:8px 10px; margin-bottom:2px;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <span style="font-weight:700; font-size:0.9rem;">{name}</span>
                      <span style="font-size:0.55rem; background:#e5e7eb; border-radius:4px;
                                    padding:1px 5px; margin-left:4px; color:#374151;">{meta['tag']}</span>
                    </div>
                    <div style="color:{color}; font-weight:700; font-size:0.8rem;">{arrow} {chg_pct:+.2f}%</div>
                  </div>
                  <div style="font-size:1.05rem; font-weight:700; margin-top:2px;">{last:,.2f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "✓ Dipilih" if is_selected else "Pilih",
                key=f"mo_pick_{name}",
                use_container_width=True,
                disabled=is_selected,
            ):
                st.session_state["mo_selected_index"] = name
                st.rerun()

    # ======================================================
    # MAIN — CHART INDEKS TERPILIH
    # ======================================================
    with col_main:

        sel_name = st.session_state["mo_selected_index"]
        sel_meta = _INDEX_OPTIONS[sel_name]
        df = idx_full.get(sel_name)
        df_intraday = idx_intraday.get(sel_name)

        if df is None or df.empty or len(df) < 2:
            st.info(f"Data {sel_name} tidak tersedia saat ini.")
        else:
            last = df["CLOSE"].iloc[-1]
            prev = df["CLOSE"].iloc[-2]
            chg = last - prev
            chg_pct = (chg / prev * 100) if prev else 0
            up = chg >= 0

            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg,#1f3d2b,#274a34); border-radius:10px;
                            padding:14px 20px; display:flex; justify-content:space-between;
                            align-items:center; color:#fff; margin-bottom:12px;">
                  <div>
                    <div style="font-size:0.65rem; letter-spacing:1px; opacity:0.75;
                                text-transform:uppercase;">{sel_meta['tag']} INDEX</div>
                    <div style="font-size:1.6rem; font-weight:800; line-height:1.15;">{sel_name}</div>
                    <div style="font-size:0.7rem; opacity:0.8;">{sel_meta['sub']}</div>
                  </div>
                  <div style="text-align:right;">
                    <div style="font-size:0.65rem; opacity:0.75;">LAST</div>
                    <div style="font-size:1.5rem; font-weight:800;">{last:,.2f}</div>
                    <div style="font-size:0.85rem; font-weight:700; color:{'#8be0ac' if up else '#ff9d9d'};">
                      {chg:+,.2f}&nbsp;&nbsp;{chg_pct:+.2f}%
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            ctrl1, ctrl2 = st.columns([1, 2])
            with ctrl1:
                chart_type = st.radio(
                    "Tipe Chart",
                    ["Line", "Candle"],
                    index=1,
                    horizontal=True,
                    label_visibility="collapsed",
                    key="mo_chart_type",
                )
            with ctrl2:
                timeframe = st.radio(
                    "Timeframe",
                    ["1D", "1M", "3M", "6M", "YTD", "1Y"],
                    index=5,
                    horizontal=True,
                    label_visibility="collapsed",
                    key="mo_timeframe",
                )

            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                row_heights=[0.75, 0.25],
                vertical_spacing=0.03,
            )

            is_intraday_view = timeframe == "1D" and df_intraday is not None and not df_intraday.empty

            if is_intraday_view:
                # ---- Tampilan 1 hari: pakai bar intraday hari sesi terakhir ----
                d_intra = df_intraday.copy()
                d_intra["_date"] = d_intra.index.date
                last_session = d_intra["_date"].max()
                df_view = d_intra[d_intra["_date"] == last_session].drop(columns=["_date"])

                # sumbu-x kategori (jam saja) supaya gap istirahat siang tidak
                # membuat candle "melompat" jauh seperti gap akhir pekan
                x_vals = [t.strftime("%H:%M") for t in df_view.index]
            else:
                now_ts = df.index.max()
                if timeframe == "YTD":
                    start_ts = pd.Timestamp(year=now_ts.year, month=1, day=1)
                else:
                    days_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
                    start_ts = now_ts - pd.Timedelta(days=days_map.get(timeframe, 365))

                df_view = df[df.index >= start_ts]
                x_vals = df_view.index

            if chart_type == "Candle":
                fig.add_trace(
                    go.Candlestick(
                        x=x_vals,
                        open=df_view["OPEN"],
                        high=df_view["HIGH"],
                        low=df_view["LOW"],
                        close=df_view["CLOSE"],
                        increasing_line_color="#2e9e63",
                        decreasing_line_color="#e05252",
                        name=sel_name,
                    ),
                    row=1, col=1,
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=x_vals,
                        y=df_view["CLOSE"],
                        mode="lines",
                        line=dict(color="#2e6e46", width=2),
                        fill="tozeroy",
                        fillcolor="rgba(46,110,70,0.15)",
                        name=sel_name,
                    ),
                    row=1, col=1,
                )

            prev_close_series = df_view["CLOSE"].shift(1).fillna(df_view["OPEN"])
            vol_colors = np.where(df_view["CLOSE"] >= prev_close_series, "#2e9e63", "#e05252")

            fig.add_trace(
                go.Bar(
                    x=x_vals,
                    y=df_view["VOLUME"],
                    marker_color=vol_colors,
                    name="Volume",
                ),
                row=2, col=1,
            )

            fig.update_layout(
                height=480,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
                xaxis_rangeslider_visible=False,
                bargap=0.2,
            )

            if is_intraday_view:
                fig.update_xaxes(showgrid=False, type="category")
                fig.update_xaxes(nticks=12, row=2, col=1)
            else:
                fig.update_xaxes(
                    showgrid=False,
                    rangebreaks=[dict(bounds=["sat", "mon"])],
                )

            fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)")

            st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "📌 Ranking di bawah dihitung dari daftar HOT_SAHAM_LIST (bukan seluruh saham IDX). "
        "Kolom **Net Asing Estimasi** adalah estimasi pola VSA dari harga & volume — "
        "**bukan data transaksi broker/asing riil**."
    )

    try:
        df_movers = _load_market_movers_data()
    except Exception as e:
        df_movers = pd.DataFrame()
        st.warning(f"Gagal memuat data top movers: {e}")

    if df_movers.empty:
        st.info("Data top movers tidak tersedia saat ini.")
        return

    _HARI_ID  = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    _BULAN_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                 "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    _last_date = df_movers["Tanggal"].max()
    st.markdown(
        f"##### 📅 Data per {_HARI_ID[_last_date.weekday()]}, "
        f"{_last_date.day} {_BULAN_ID[_last_date.month]} {_last_date.year}"
    )

    tab_gainer, tab_loser, tab_volume, tab_asing = st.tabs(
        ["🟢 Top Gainer", "🔴 Top Loser", "📊 Top Volume", "🌐 Top Net Asing (Estimasi)"]
    )

    with tab_gainer:
        top_gainer = df_movers.sort_values("Perubahan (%)", ascending=False).head(10)
        st.dataframe(
            top_gainer[["Kode", "Close", "Perubahan (%)", "Volume"]],
            use_container_width=True,
            hide_index=True,
        )

    with tab_loser:
        top_loser = df_movers.sort_values("Perubahan (%)", ascending=True).head(10)
        st.dataframe(
            top_loser[["Kode", "Close", "Perubahan (%)", "Volume"]],
            use_container_width=True,
            hide_index=True,
        )

    with tab_volume:
        top_volume = df_movers.sort_values("Volume", ascending=False).head(10)
        st.dataframe(
            top_volume[["Kode", "Close", "Perubahan (%)", "Volume"]],
            use_container_width=True,
            hide_index=True,
        )

    with tab_asing:
        top_asing = df_movers.sort_values("Net Asing Estimasi (Rp)", ascending=False).head(10)
        st.dataframe(
            top_asing[["Kode", "Close", "Perubahan (%)", "Net Asing Estimasi (Rp)"]],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()


# ==========================================================
# ===================== MAIN UI =============================
# ==========================================================

def render_screener():

    st.header("📊 Stock Screener")

    render_market_overview()

    with st.expander("📌 **Important Notes**"):

        st.markdown(
            """
    - Sebelum menggunakan screener, disarankan membaca panduan di menu **📘 Strategy Guide**
    - Untuk menu **ARA Hunter** dan **BSJP**, lakukan scan beberapa kali jika hasil tidak ditemukan atau hanya sedikit, karena:
        - Scanner berjalan sangat cepat sehingga memungkinkan beberapa emiten terlewat pada scan tertentu
        - Re-scan biasanya dapat membantu menangkap momentum dan kandidat tambahan
    """
        )

    import subprocess

    # ======================================================
    # PATH
    # ======================================================

    BASE_DIR = os.getcwd()

    HOT_SCRIPT = os.path.join(
        BASE_DIR,
        "app",
        "config",
        "convert_idx_hot.py"
    )

    # ======================================================
    # GENERATE HOT LIST
    # ======================================================

    ADMIN_USERS = ["Ridho Pradana"]

    current_user = st.session_state.get("username", "").strip()

    if current_user in ADMIN_USERS:

        if st.button("🔥 Re-generate HOT List"):

            try:

                with st.spinner("Generating HOT_SAHAM_LIST..."):

                    result = subprocess.run(

                        [sys.executable, HOT_SCRIPT],

                        capture_output=True,
                        text=True

                    )

                    if result.returncode == 0:
                        st.success("HOT_SAHAM_LIST generated successfully!")

                    else:
                        st.error("Failed generating HOT_SAHAM_LIST")
                        st.code(result.stderr)

            except Exception as e:
                st.error(f"Error: {e}")

    # ======================================================
    # SELECT TYPE
    # ======================================================

    screener_type = st.selectbox(

        "Pilih Tipe",

        [
            "Fast Trade (ARA Hunter)",
            "Swing Trade (Day-Week)",
            "Beli Sore Jual Pagi (BSJP)"
        ]
    )

    # ======================================================
    # INIT STATE
    # ======================================================

    if "scanner_state" not in st.session_state:

        st.session_state["scanner_state"] = {

            "alerted": {},

            "last_status": {}
        }

    # ======================================================
    # SCAN BUTTON
    # ======================================================

    if st.button(
        "🚀 Scan Market",
        use_container_width=True
    ):

        with st.spinner(
            "Scanning market..."
        ):

            # ==================================================
            # ARA HUNTER
            # ==================================================

            if "ARA Hunter" in screener_type:

                df, alerts, state = scan_day(
                    st.session_state["scanner_state"]
                )

                if not df.empty:

                    sort_cols = []

                    if "Score" in df.columns:
                        sort_cols.append("Score")

                    if "Volume" in df.columns:
                        sort_cols.append("Volume")

                    if sort_cols:

                        df = df.sort_values(

                            by=sort_cols,

                            ascending=False
                        )

                    df = df.head(20)

                st.session_state[
                    "scanner_state"
                ] = state

                st.session_state["mode"] = "day"

                st.session_state["data"] = df

            # ==================================================
            # BSJP
            # ==================================================

            elif (
                screener_type
                ==
                "Beli Sore Jual Pagi (BSJP)"
            ):

                df, alerts, state = scan_bsjp(
                    st.session_state["scanner_state"]
                )

                st.session_state[
                    "scanner_state"
                ] = state

                st.session_state["mode"] = "bsjp"

                st.session_state["data"] = df

            # ==================================================
            # WEEK
            # ==================================================

            else:

                entry_df = pd.DataFrame()

                watchlist_df = pd.DataFrame()

                try:

                    entry_df, watchlist_df = scan_week()

                except Exception as e:

                    st.error(
                        f"Scan error: {e}"
                    )

                st.session_state["mode"] = "week"

                st.session_state["entry_data"] = entry_df

                st.session_state["watchlist_data"] = watchlist_df

            st.session_state["time"] = (
                datetime.now(tz)
                .strftime("%d %b %H:%M:%S")
            )

    # ======================================================
    # DISPLAY
    # ======================================================

    if "mode" not in st.session_state:
        return

    st.caption(
        f"⏱ Last Scan: "
        f"{st.session_state.get('time','-')}"
    )

    # ======================================================
    # DAY
    # ======================================================

    if st.session_state["mode"] == "day":

        st.subheader(
            "⚡ ARA HUNTER"
        )

        df = st.session_state.get(
            "data",
            pd.DataFrame()
        )

        if df.empty:

            st.warning(
                "📭 Tidak ada data"
            )

        else:

            st.dataframe(
                df,
                use_container_width=True
            )

    # ======================================================
    # BSJP
    # ======================================================

    elif st.session_state["mode"] == "bsjp":

        st.subheader(
            "🎯 BSJP SETUP"
        )

        df = st.session_state.get(
            "data",
            pd.DataFrame()
        )

        if df.empty:

            st.warning(
                "📭 Tidak ada kandidat BSJP"
            )

        else:

            st.dataframe(
                df,
                use_container_width=True
            )

    # ======================================================
    # WEEK
    # ======================================================

    else:

        # ==================================================
        # ENTRY READY
        # ==================================================

        st.subheader(
            "🚀 READY ENTRY"
        )

        entry_df = st.session_state.get(
            "entry_data",
            pd.DataFrame()
        )

        if entry_df.empty:

            st.warning(
                "📭 Tidak ada setup entry"
            )

        else:

            st.dataframe(
                entry_df,
                use_container_width=True
            )

        # ==================================================
        # WATCHLIST
        # ==================================================

        st.divider()

        st.subheader(
            "👀 WATCHLIST"
        )

        watchlist_df = st.session_state.get(
            "watchlist_data",
            pd.DataFrame()
        )

        if watchlist_df.empty:

            st.warning(
                "📭 Tidak ada watchlist"
            )

        else:

            st.dataframe(
                watchlist_df,
                use_container_width=True
            )

        # ==================================================
        # TELEGRAM
        # ==================================================

        st.divider()

        st.subheader(
            "📤 Share Screener Result"
        )

        try:
            SHARE_PASSWORD = st.secrets.get("SHARE_PASSWORD") or os.getenv("SHARE_PASSWORD")
        except Exception:
            SHARE_PASSWORD = os.getenv("SHARE_PASSWORD")

        df_ihsg = get_price_data("^JKSE")

        input_pwd = st.text_input(

            "🔐 Password untuk kirim Telegram",

            type="password",

            key="share_pwd_screener",
        )

        is_authorized = (
            input_pwd == SHARE_PASSWORD
        )

        if st.button(

            "📨 Send Screener to Telegram",

            type="primary",

            use_container_width=True,

            disabled=not is_authorized,
        ):

            try:

                results = []

                if not entry_df.empty:

                    results.extend(
                        entry_df.to_dict(
                            orient="records"
                        )
                    )

                if not watchlist_df.empty:

                    results.extend(
                        watchlist_df.to_dict(
                            orient="records"
                        )
                    )

                if not results:

                    st.warning(
                        "Tidak ada data untuk dikirim"
                    )

                else:

                    msg = render_telegram(
                        results,
                        df_ihsg=df_ihsg
                    )

                    send_message(msg)

                    st.success(
                        "Terkirim ke Telegram ✅"
                    )

            except Exception as e:

                st.error(
                    "❌ Gagal kirim ke Telegram"
                )

                st.code(str(e))

# ==========================================================
# =================== TRADING TRACKER ======================
# ==========================================================
from datetime import datetime, timedelta

def format_holding_days(days):
    if days is None or days == 0:
        return "0 hari"

    years = days // 365
    months = (days % 365) // 30
    remaining_days = (days % 365) % 30

    parts = []
    if years:
        parts.append(f"{years} thn -")
    if months:
        parts.append(f"{months} bln -")
    if remaining_days:
        parts.append(f"{remaining_days} hari")

    return " ".join(parts)


def render_trading_summary():
    if not require_trading_password():
        return

    st.header("📊 Trading Tracker - Summary")

    from app.tracker.storage import use_gsheets
    if not use_gsheets():
        st.warning(
            "⚠️ Google Sheets belum dikonfigurasi — data tersimpan di file "
            "lokal dan akan **hilang setiap redeploy** di Streamlit Cloud. "
            "Set `gcp_service_account` dan `TRACKER_SHEET_ID` di Secrets."
        )

    import pandas as pd

    # ===================== BUY =====================
    with st.form("add_buy"):
        st.subheader("➕ Catat BUY")

        col1, col2 = st.columns(2)
        with col1:
            kode = st.selectbox("Kode Saham", SAHAM_LIST)
            buy_price = st.number_input("Harga Beli", min_value=0)
            buy_lot = st.number_input("Lot", min_value=1, value=1)

        with col2:
            buy_date = st.date_input("Tanggal Beli", value=date.today())
            note = st.text_input("Catatan (opsional)")

        submitted_buy = st.form_submit_button("Simpan BUY")

        if submitted_buy:
            if buy_price < 1:
                st.error("❌ Harga beli minimal 1")
            else:
                save_buy(kode, buy_date, buy_price, buy_lot, note)
                st.success("BUY dicatat ✅")
                st.rerun()

    # ===================== LOAD DATA =====================
    df_trades = enrich_trades(load_trades())
    df_div = load_dividends()

    st.subheader("📊 Trading Summary")

    if df_trades.empty:
        st.info("Belum ada trade yang tercatat.")
        return

    df_trades["Modal"] = df_trades["Buy"] * df_trades["Sisa Lot"] * 100

    total_modal = df_trades["Modal"].sum()
    total_capital = df_trades["PnL (Rp)"].sum()
    total_dividend = df_div["amount"].sum() if not df_div.empty else 0
    total_profit = total_capital + total_dividend
    profit_pct = (total_profit / total_modal * 100) if total_modal > 0 else 0

    def rp(x):
        return f"Rp {int(x):,}".replace(",", ".")

    # ===================== METRICS =====================
    c1, c2, c3 = st.columns(3)
    c1.metric("Modal", rp(total_modal))
    c2.metric("Capital Gain", rp(total_capital))
    c3.metric("Dividend", rp(total_dividend))

    c4, c5, spacer = st.columns(3)
    c4.metric("Total Profit", rp(total_profit))
    c5.metric("Profit %", f"{profit_pct:.1f}%")
    spacer.empty()

    st.divider()

    # ===================== TRADING HISTORY =====================
    st.subheader("📋 Trading History")

    table_df = df_trades.copy()

    # Nama perusahaan
    table_df["Nama"] = table_df["Kode"].apply(
        lambda x: SAHAM_PROFILE.get(x, x)
    )

    # Format tanggal
    table_df["Buy Date"] = table_df["buy_date"].apply(format_date_indo)
    table_df["Sell Date"] = table_df["Sell Date"].apply(format_date_indo)

    # Format holding days
    table_df["Holding Days"] = table_df["Holding Days"].apply(format_holding_days)

    # Sorting terbaru
    table_df = table_df.sort_values("buy_date", ascending=False)

    table_df = table_df[
        [
            "Kode",
            "Nama",
            "Buy Date",
            "Sell Date",
            "Buy",
            "Now",
            "Sisa Lot",
            "Status",
            "Holding Days",
            "PnL (Rp)",
            "PnL (%)",
        ]
    ]

    table_df["PnL (Rp)"] = table_df["PnL (Rp)"].apply(rp)
    table_df["PnL (%)"] = table_df["PnL (%)"].apply(lambda x: f"{x:.1f}%")

    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # ===================== DIVIDEND HISTORY =====================
    st.subheader("💰 Dividend History")

    if df_div.empty:
        st.info("Belum ada dividen tercatat.")
    else:
        div_table = df_div.copy()

        # Ambil kode dari trade
        div_table["Kode"] = div_table["trade_id"].apply(
            lambda i: df_trades.loc[i, "Kode"] if i in df_trades.index else "-"
        )

        # Nama perusahaan
        div_table["Nama"] = div_table["Kode"].apply(
            lambda x: SAHAM_PROFILE.get(x, x)
        )

        div_table["date"] = pd.to_datetime(div_table["date"])

        # Sort: kode → tanggal terbaru
        div_table = div_table.sort_values(
            by=["Kode", "date"],
            ascending=[True, False]
        )

        # Format tanggal
        div_table["Tanggal"] = div_table["date"].apply(
            lambda x: x.strftime("%d-%b-%Y")
        )

        # Format rupiah
        div_table["Dividen"] = div_table["amount"].apply(rp)

        show_df = div_table[["Kode", "Nama", "Tanggal", "Dividen"]]

        st.dataframe(
            show_df,
            use_container_width=True,
            hide_index=True
        )

    # ===================== TAMBAH DIVIDEN =====================
    df = load_trades()
    st.subheader("➕ Tambah Dividen")

    idx_div = st.selectbox(
        "Pilih Trade",
        df.index,
        format_func=lambda i: f"{df.loc[i,'kode']} | {df.loc[i,'remaining_lot']} lot"
    )

    div_date = st.date_input("Tanggal Dividen", value=date.today())
    div_amount = st.number_input("Nominal Dividen (Rp)", min_value=0)

    if st.button("Simpan Dividen"):
        if div_amount < 1:
            st.error("❌ Nominal dividen minimal 1")
        else:
            save_dividend(idx_div, div_date, div_amount)
            st.session_state["div_success"] = True
            st.rerun()

    if "div_success" in st.session_state:
        st.success("✅ Dividen berhasil disimpan")
        del st.session_state["div_success"]



def render_manage_data():
    if not require_trading_password():
        return
    st.header("⚙️ Trading Tracker - Manage Data")

    import pandas as pd

    df_trades = enrich_trades(load_trades())
    df_div = load_dividends()

    # ===================== SELL =====================
    df = load_trades()
    df["remaining_lot"] = pd.to_numeric(df["remaining_lot"], errors="coerce").fillna(0).astype(int)
    open_trades = df[df["remaining_lot"] > 0]

    if not open_trades.empty:
        st.subheader("✏️ Jual")

        idx = st.selectbox(
            "Pilih posisi",
            open_trades.index,
            format_func=lambda i: f"{df.loc[i,'kode']} | {df.loc[i,'remaining_lot']} lot",
        )

        remaining_lot = int(df.loc[idx, "remaining_lot"])

        sell_price = st.number_input("Harga Jual", min_value=0)
        sell_lot = st.number_input("Lot Dijual", min_value=0, value=0)
        sell_date = st.date_input("Tanggal Jual", value=date.today())

        if st.button("Jual"):
            errors = []

            if sell_price < 1:
                errors.append("Harga jual minimal 1")

            if sell_lot < 1:
                errors.append("Lot jual minimal 1")

            if sell_lot > remaining_lot:
                errors.append(f"Lot jual tidak boleh lebih dari {remaining_lot}")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                save_sell(idx, sell_date, sell_price, sell_lot)
                st.success("Transaksi jual tercatat")
                st.rerun()

    # ===================== DELETE TRADE =====================
    st.divider()
    st.subheader("🗑️ Hapus Trade")

    selected_idx = st.selectbox(
        "Pilih trade",
        df_trades.index,
        format_func=lambda i: f"{df_trades.loc[i,'Kode']} | {df_trades.loc[i,'Buy']}"
    )

    if st.button("Hapus Trade"):
        st.session_state["confirm_delete_trade"] = selected_idx

    if "confirm_delete_trade" in st.session_state:
        idx_confirm = st.session_state["confirm_delete_trade"]

        st.warning("⚠️ Anda yakin ingin menghapus trade ini beserta semua dividennya?")

        col1, col2 = st.columns(2)

        if col1.button("❌ Batal"):
            del st.session_state["confirm_delete_trade"]

        if col2.button("🗑️ Ya, Hapus Permanen"):
            delete_trade(idx_confirm)
            delete_dividends_by_trade(idx_confirm)
            del st.session_state["confirm_delete_trade"]
            st.success("Trade & dividen terkait berhasil dihapus")
            st.rerun()

    # ===================== DELETE DIVIDEND =====================
    st.subheader("🧾 Hapus Dividen")

    if df_div.empty:
        st.info("Belum ada dividen untuk dihapus.")
    else:
        div_options = df_div.reset_index()

        def format_div_option(i):
            trade_id = div_options.loc[i, "trade_id"]

            if trade_id in df_trades.index:
                kode = df_trades.loc[trade_id, "Kode"]
            else:
                kode = "(Trade sudah dihapus)"

            tanggal = div_options.loc[i, "date"]
            amount = f"Rp {int(div_options.loc[i,'amount']):,}".replace(",", ".")

            return f"{kode} | {tanggal} | {amount}"

        selected_div = st.selectbox(
            "Pilih dividen",
            div_options["index"],
            format_func=format_div_option
        )

        if st.button("Hapus Dividen"):
            st.session_state["confirm_delete_div"] = selected_div

        if "confirm_delete_div" in st.session_state:
            idx_div_confirm = st.session_state["confirm_delete_div"]

            st.warning("⚠️ Anda yakin ingin menghapus dividen ini?")

            col1, col2 = st.columns(2)

            if col1.button("❌ Batal", key="cancel_div"):
                del st.session_state["confirm_delete_div"]

            if col2.button("🗑️ Ya, Hapus", key="confirm_div"):
                df_div2 = load_dividends()
                df_div2 = df_div2.drop(idx_div_confirm)
                save_dividends(df_div2)

                del st.session_state["confirm_delete_div"]
                st.success("Dividen berhasil dihapus")
                st.rerun()

# ==========================================================
# =================== STRATEGY GUIDE =======================
# ==========================================================

def render_strategy_guide():

    st.header("📘 Trading Strategy Guide")

    st.caption(
        "Panduan penggunaan strategy, "
        "timing screener, dan manajemen risiko."
    )

    # ======================================================
    # ARA HUNTER
    # ======================================================

    st.subheader("🚀 ARA Hunter")

    st.markdown("""

### Deskripsi
Strategi momentum agresif untuk mencari saham yang berpotensi lanjut ARA atau breakout kuat saat market baru buka.

### Cara Menjalankan
- Jalankan sekitar jam **09.01 – 09.15 pagi** untuk sesi pertama
- Jalankan sekitar jam **13.31 – 13.45 siang** untuk sesi kedua, hari Jumat bisa disesuaikan
- Fokus ke **1–2 saham** dengan:
  - score tinggi
  - volume besar
  - momentum paling kuat

### Entry
- Bisa entry dengan cara nyicil mengikuti momentum
- Jika harga pullback, boleh lanjut cicil di area support terdekat

### Risk Management
- **TP1:** sekitar **4–6%**
- **TP2:** sekitar **7–9%**
- **SL:** sekitar **8%**

### Karakter
- High risk
- High volatility
- Cocok saat market bullish dan ramai momentum

""")

    st.divider()

    # ==========================================================
    # SWING TRADE
    # ==========================================================

    st.subheader("📈 Swing Trade (Day–Week)")

    st.markdown("""

### Deskripsi
Strategi swing trading untuk mencari saham dengan trend yang masih sehat, momentum kuat, dan potensi continuation dalam beberapa hari hingga beberapa minggu.

Fokus utama strategi ini:
- trend bullish sehat
- pullback / rebound
- continuation setup
- smart money accumulation
- cycle timing

### Cara Menjalankan
- Jalankan screener sekitar jam **00.00 – 09.00 pagi** sebelum market buka
- Pilih **1–3 saham** dengan:
  - score tinggi
  - volume besar
  - liquidity bagus
  - atau saham favorit untuk dianalisa lebih dalam

### Analisa Tambahan
Setelah kandidat ditemukan, lakukan analisa lanjutan menggunakan:
- menu **Stock Analysis**
- chart pribadi
- atau analisa discretionary tambahan

Beberapa hal yang perlu diperhatikan:
- Status trend
- Support & resistance
- Gap analysis
- Smart money
- Volume & volatility
- Risk / reward area

### Ketentuan Penting

#### 📈 Overvalued tapi Trend Masih Kuat
Jika saham sudah:
- cukup tinggi / extended
- dekat resistance
- atau mulai overvalued

tetapi:
- trend masih sangat kuat
- volume tetap sehat
- smart money masih masuk
- momentum belum melemah

maka resistance masih berpotensi:
- ditembus
- atau terjadi continuation breakout

Karena dalam strong trend:
> harga bisa tetap naik lebih lama dari ekspektasi market.

#### 📉 Oversold tapi Trend Masih Melemah
Sebaliknya, jika saham:
- sudah oversold
- volume masih melemah
- momentum belum pulih
- gagal rebound dari support
- atau smart money masih keluar

maka support terdekat berpotensi:
- jebol
- atau terjadi breakdown lebih dalam

Karena dalam weak trend:
> saham oversold tetap bisa lanjut turun sebelum benar-benar reversal.

### Entry
- Idealnya entry dilakukan:
  - dekat support
  - saat pullback sehat
  - atau saat rebound mulai terkonfirmasi

- Hindari entry terlalu jauh dari support jika momentum mulai melemah

### Risk Management
- **TP:** fleksibel mengikuti resistance dan trend strength
- **SL:** idealnya di bawah support terdekat atau invalidation area

### Karakter
- Medium risk
- Cocok untuk posisi beberapa hari hingga mingguan
- Lebih fleksibel dibanding ARA Hunter
- Lebih fokus ke probability dan kualitas trend

""")

    st.divider()

    # ======================================================
    # BSJP SCENARIO 1
    # ======================================================

    st.subheader("🌙 BSJP — Skenario 1 (Freeze Time)")

    st.markdown("""

### Deskripsi
Strategi mencari saham yang masih diakumulasi menjelang market tutup dan berpotensi gap up keesokan harinya.

### Cara Menjalankan

#### Sesi Pertama
- Jalankan screener jam **15.15 – 15.30 sore**
- Pilih **1–3 saham** dengan:
  - score tinggi
  - volume besar
  - buy pressure kuat

#### Sesi Konfirmasi
- Jalankan ulang screener jam **15.50 – 16.00 sore** sebelum market tutup
- Fokus pada saham yang muncul kembali di screener

### Entry
- Entry saat freeze time sekitar **15.50 – 16.00**
- Pasang buy sekitar **2–3 tick di atas harga terakhir**

### Exit Plan
- Besok pagi langsung pasang:
  - **TP1:** sekitar **3–4%**
  - **TP2:** sekitar **6–7%**
  - **SL:** sekitar **8%**

### Karakter
- Overnight setup
- Mengandalkan closing accumulation
- Cocok untuk market bullish atau sideways bullish

""")

    st.divider()

    # ======================================================
    # BSJP SCENARIO 2
    # ======================================================

    st.subheader("🌅 BSJP — Skenario 2 (Pre-Market Setup)")

    st.markdown("""

### Deskripsi
Strategi overnight sebelum market buka dengan fokus pada saham yang masih memiliki potensi continuation.

### Cara Menjalankan
- Jalankan screener sekitar jam **00.00 – 09.00 pagi** sebelum market buka
- Pilih **1–2 saham** dengan:
  - score tinggi
  - volume kuat
  - setup paling bersih

### Entry
- Sebelum market buka, perhatikan area IEP (Indicative Equilibrium Price)
- Idealnya pasang buy sekitar **2–3 tick di atas area IEP** agar peluang match lebih besar
- Setelah entry, langsung pasang:
  - Buy
  - TP
  - SL sekaligus

### Exit Plan
- Langsung pasang:
  - **TP1:** sekitar **3–4%**
  - **TP2:** sekitar **6–7%**
  - **SL:** sekitar **8%**

### Karakter
- Lebih konservatif dibanding ARA Hunter
- Cocok untuk continuation swing pendek
- Lebih nyaman untuk trader yang tidak ingin terlalu agresif intraday

""")

# ==========================================================
# =========== MULTI-ALGO SCREENER ==========================
# ==========================================================

def render_multi_algo_screener():

    st.title("🧠 Multi-Algorithm Screener")
    st.caption(
        "Pilih kombinasi algoritma teknikal untuk filter saham. "
        "Setiap algoritma memberikan sinyal yang digabungkan menjadi skor akhir."
    )

    st.divider()

    # --------------------------------------------------
    # SIDEBAR CONFIG
    # --------------------------------------------------
    with st.sidebar:
        st.subheader("⚙️ Konfigurasi Algoritma")

        st.markdown("**Pilih Algoritma Aktif**")

        use_rsi        = st.checkbox("RSI",              value=True)
        use_macd       = st.checkbox("MACD",             value=True)
        use_bb         = st.checkbox("Bollinger Bands",  value=True)
        use_ema_cross  = st.checkbox("EMA Cross",        value=True)
        use_adx        = st.checkbox("ADX",              value=True)
        use_supertrend = st.checkbox("Supertrend",       value=True)
        use_stoch_rsi  = st.checkbox("Stochastic RSI",  value=True)
        use_obv        = st.checkbox("OBV",              value=True)
        use_mfi        = st.checkbox("MFI",              value=False)
        use_cci        = st.checkbox("CCI",              value=False)
        use_williams_r = st.checkbox("Williams %R",     value=False)

        st.divider()
        st.markdown("**Filter**")
        min_score  = st.slider("Skor Minimum", 0, 100, 55, step=5)
        min_volume = st.number_input("Volume Minimum", value=1_000_000, step=500_000)

        st.divider()
        st.markdown("**Parameter RSI**")
        rsi_period = st.slider("RSI Period", 5, 30, 14)
        rsi_ob     = st.slider("RSI Overbought", 60, 90, 70)
        rsi_os     = st.slider("RSI Oversold",   10, 40, 30)

        st.divider()
        st.markdown("**Parameter EMA Cross**")
        ema_fast = st.slider("EMA Fast", 3, 20, 9)
        ema_slow = st.slider("EMA Slow", 10, 50, 21)

        st.divider()
        st.markdown("**Parameter ADX**")
        adx_threshold = st.slider("ADX Threshold (tren kuat)", 15, 40, 25)

        st.divider()
        st.markdown("**Parameter Supertrend**")
        st_period     = st.slider("Supertrend Period",     5, 20, 10)
        st_multiplier = st.slider("Supertrend Multiplier", 1.0, 5.0, 3.0, step=0.5)

    # --------------------------------------------------
    # DAFTAR SAHAM
    # --------------------------------------------------
    col1, col2 = st.columns([3, 1])
    with col1:
        scan_mode = st.radio(
            "Daftar Saham",
            ["Semua Saham (default)", "Input Manual"],
            horizontal=True
        )

    saham_to_scan = SAHAM_LIST

    if scan_mode == "Input Manual":
        raw = st.text_area(
            "Masukkan kode saham (pisahkan dengan koma atau enter)",
            placeholder="BBCA, BMRI, TLKM, ASII"
        )
        if raw.strip():
            saham_to_scan = [
                s.strip().upper()
                for s in raw.replace("\n", ",").split(",")
                if s.strip()
            ]

    # --------------------------------------------------
    # CONFIG OBJECT
    # --------------------------------------------------
    config = {
        **DEFAULT_CONFIG,
        "use_rsi":          use_rsi,
        "use_macd":         use_macd,
        "use_bb":           use_bb,
        "use_ema_cross":    use_ema_cross,
        "use_adx":          use_adx,
        "use_supertrend":   use_supertrend,
        "use_stoch_rsi":    use_stoch_rsi,
        "use_obv":          use_obv,
        "use_mfi":          use_mfi,
        "use_cci":          use_cci,
        "use_williams_r":   use_williams_r,
        "rsi_period":       rsi_period,
        "rsi_ob":           rsi_ob,
        "rsi_os":           rsi_os,
        "ema_fast":         ema_fast,
        "ema_slow":         ema_slow,
        "adx_threshold":    adx_threshold,
        "st_period":        st_period,
        "st_multiplier":    float(st_multiplier),
        "min_volume":       int(min_volume),
        "min_score":        min_score,
    }

    active_algos = sum([
        use_rsi, use_macd, use_bb, use_ema_cross,
        use_adx, use_supertrend, use_stoch_rsi, use_obv,
        use_mfi, use_cci, use_williams_r
    ])

    st.info(
        f"**{active_algos} algoritma aktif** · "
        f"{len(saham_to_scan)} saham akan discan · "
        f"Skor minimum: {min_score}"
    )

    # --------------------------------------------------
    # SCAN
    # --------------------------------------------------
    if st.button("🧠 Jalankan Multi-Algo Scan", use_container_width=True):

        if active_algos == 0:
            st.warning("Pilih minimal 1 algoritma terlebih dahulu.")
            return

        with st.spinner(f"Scanning {len(saham_to_scan)} saham dengan {active_algos} algoritma..."):
            results = scan_multi_algo(saham_to_scan, config)

        if not results:
            st.warning("Tidak ada saham yang lolos filter. Coba turunkan skor minimum.")
            return

        st.success(f"✅ Ditemukan **{len(results)} saham** yang lolos filter")
        st.divider()

        # --------------------------------------------------
        # TABEL RINGKASAN
        # --------------------------------------------------
        rows = []
        for r in results:
            rows.append({
                "Kode":          r["kode"],
                "Harga":         r["price"],
                "Skor":          r["score"],
                "Rekomendasi":   r["recommendation"],
                "Vol Ratio":     r["vol_ratio"],
                "Entry":         r["entry"],
                "SL":            r["sl"],
                "TP1":           r["tp1"],
                "TP2":           r["tp2"],
                "R/R":           r["rr"],
                "ATR":           r["atr"],
                "Algo Aktif":    r["active_algos"],
            })

        df_results = pd.DataFrame(rows)
        st.dataframe(df_results, use_container_width=True, hide_index=True)

        st.divider()

        # --------------------------------------------------
        # DETAIL SINYAL PER SAHAM
        # --------------------------------------------------
        st.subheader("📊 Detail Sinyal Per Saham")

        for r in results:
            kode = r["kode"]
            nama = SAHAM_PROFILE.get(kode, kode)

            with st.expander(
                f"{r['recommendation']} — **{kode}** ({nama}) | "
                f"Skor: {r['score']} | Harga: {r['price']:,}",
                expanded=False
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry",  f"{r['entry']:,}")
                c2.metric("SL",     f"{r['sl']:,}")
                c3.metric("TP1",    f"{r['tp1']:,}")
                c4.metric("TP2",    f"{r['tp2']:,}")

                c5, c6, c7 = st.columns(3)
                c5.metric("R/R",        r["rr"])
                c6.metric("ATR",        f"{r['atr']:,}")
                c7.metric("Vol Ratio",  r["vol_ratio"])

                st.markdown("**Sinyal per Algoritma:**")

                sig_rows = []
                for algo_name, sig_data in r["signals"].items():
                    score_val = sig_data.get("score", "-")
                    signal_val = sig_data.get("signal", "-")
                    emoji = (
                        "🟢" if score_val >= 70
                        else "🟡" if score_val >= 50
                        else "🔴"
                    )
                    sig_rows.append({
                        "Algoritma": f"{emoji} {algo_name}",
                        "Sinyal":    signal_val,
                        "Skor":      score_val,
                    })

                st.dataframe(
                    pd.DataFrame(sig_rows),
                    use_container_width=True,
                    hide_index=True
                )

# ==========================================================
# ==================== CPO MONITORING =========================
# ==========================================================

def render_cpo_monitor():
    import matplotlib.pyplot as plt
    from app.utils.cpo_engine import (
        get_cpo_global, get_cpo_indonesia, cpo_summary,
        get_cpo_news, get_cpo_wordcloud,
        get_minyakgoreng_current, get_minyakgoreng_history, get_minyakgoreng_all_history,
        get_minyakgoreng_news,
    )

    st.title("🌿 CPO dan Minyak Goreng Monitoring Kebun")
    st.caption("Pantau harga Crude Palm Oil global & lokal Indonesia beserta analisis sentimen berita.")
    st.divider()

    tab_harga, tab_minyak, tab_sentimen, tab_forecast = st.tabs([
        "📈 Harga CPO & Trend", "🛢️ Minyak Goreng Jatim",
        "📰 Sentimen Berita", "🔮 Analisis Forecast",
    ])

    # =========================================================
    # TAB 1 — HARGA & TREND
    # =========================================================
    with tab_harga:
        period = st.selectbox(
            "Periode historis",
            ["3mo", "6mo", "1y", "2y", "5y"],
            index=2,
            key="cpo_period"
        )

        col_load, _ = st.columns([1, 3])
        with col_load:
            load = st.button("🔄 Muat Data Harga", use_container_width=True)

        if load or st.session_state.get("cpo_data_loaded"):
            if load:
                with st.spinner("Mengambil data harga CPO global & lokal..."):
                    df_global  = get_cpo_global(period)
                    df_indo    = get_cpo_indonesia(period)
                _HARI_ID_C  = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
                _BULAN_ID_C = ["","Januari","Februari","Maret","April","Mei","Juni",
                               "Juli","Agustus","September","Oktober","November","Desember"]
                _now_c = datetime.now()
                _ts_c  = (f"{_HARI_ID_C[_now_c.weekday()]}, "
                          f"{_now_c.day} {_BULAN_ID_C[_now_c.month]} {_now_c.year}  "
                          f"{_now_c.strftime('%H:%M')} WIB")
                st.session_state["cpo_global"]      = df_global
                st.session_state["cpo_indo"]        = df_indo
                st.session_state["cpo_period_sel"]  = period
                st.session_state["cpo_data_loaded"] = True
                st.session_state["cpo_loaded_at"]   = _ts_c
            else:
                df_global = st.session_state.get("cpo_global", pd.DataFrame())
                df_indo   = st.session_state.get("cpo_indo",   pd.DataFrame())

            # ---- GLOBAL ----
            _src_global = df_global["Source"].iloc[-1] if not df_global.empty and "Source" in df_global.columns else ""
            _cur_global = df_global["Currency"].iloc[-1] if not df_global.empty and "Currency" in df_global.columns else "USD"
            _cpo_loaded_at = st.session_state.get("cpo_loaded_at", "")
            st.subheader("🌍 Harga CPO Global")
            if _cpo_loaded_at:
                st.caption(f"🕐 Data diperbarui: **{_cpo_loaded_at}**")
            if _src_global:
                st.caption(f"Sumber: {_src_global}")
            if df_global.empty:
                st.warning("Data global tidak tersedia. Cek koneksi internet.")
            else:
                g = cpo_summary(df_global, "Close")
                if g:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric(f"Harga Terkini ({_cur_global}/ton)",
                               f"{_cur_global} {g['current']:,.2f}",
                               f"{g['chg_pct']:+.2f}%")
                    c2.metric("Harga (IDR/ton)",
                               f"Rp {df_global['Close_IDR'].iloc[-1]:,.0f}")
                    c3.metric("52W High", f"{_cur_global} {g['high_52w']:,.2f}")
                    c4.metric("52W Low",  f"{_cur_global} {g['low_52w']:,.2f}")

                # Grafik Close + MA
                fig, ax = plt.subplots(figsize=(12, 4))
                ax.plot(df_global["Date"], df_global["Close"],
                        label=f"Harga CPO ({_cur_global})", linewidth=2, color="#2196F3")
                if "MA20" in df_global.columns:
                    ax.plot(df_global["Date"], df_global["MA20"],
                            label="MA20", linestyle="--", color="#FF9800")
                if "MA50" in df_global.columns:
                    ax.plot(df_global["Date"], df_global["MA50"],
                            label="MA50", linestyle="--", color="#F44336")
                ax.set_title(f"Trend Harga CPO Global ({_cur_global}/ton)")
                ax.set_ylabel(f"{_cur_global} / ton")
                ax.legend()
                ax.grid(alpha=0.3)
                plt.xticks(rotation=30)
                plt.tight_layout()
                st.pyplot(fig)

                # Grafik IDR
                fig2, ax2 = plt.subplots(figsize=(12, 3))
                ax2.fill_between(df_global["Date"], df_global["Close_IDR"],
                                 alpha=0.4, color="#4CAF50")
                ax2.plot(df_global["Date"], df_global["Close_IDR"],
                         color="#4CAF50", linewidth=1.5)
                ax2.set_title("Harga CPO Global dalam IDR/ton")
                ax2.set_ylabel("Rp / ton")
                ax2.grid(alpha=0.3)
                plt.xticks(rotation=30)
                plt.tight_layout()
                st.pyplot(fig2)

            st.divider()

            # ---- LOKAL INDONESIA ----
            st.subheader("🇮🇩 Harga CPO Lokal Indonesia")
            if df_indo.empty:
                st.warning("Data lokal tidak tersedia.")
            else:
                src = df_indo.get("Source", pd.Series(["FCPO.KL (estimasi IDR)"])).iloc[-1]
                st.caption(f"Sumber: {src}")

                g2 = cpo_summary(df_indo, "Close_IDR")
                if g2:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Harga Terkini (IDR/ton)",
                               f"Rp {g2['current']:,.0f}",
                               f"{g2['chg_pct']:+.2f}%")
                    c2.metric("52W High", f"Rp {g2['high_52w']:,.0f}")
                    c3.metric("52W Low",  f"Rp {g2['low_52w']:,.0f}")

                fig3, ax3 = plt.subplots(figsize=(12, 4))
                ax3.plot(df_indo["Date"], df_indo["Close_IDR"],
                         label="CPO Lokal (IDR/ton)", linewidth=2, color="#8BC34A")
                if "MA20" in df_indo.columns:
                    ax3.plot(df_indo["Date"], df_indo["MA20"],
                             label="MA20", linestyle="--", color="#FF9800")
                if "MA50" in df_indo.columns:
                    ax3.plot(df_indo["Date"], df_indo["MA50"],
                             label="MA50", linestyle="--", color="#F44336")
                ax3.set_title("Trend Harga CPO Lokal Indonesia (IDR/ton)")
                ax3.set_ylabel("Rp / ton")
                ax3.legend()
                ax3.grid(alpha=0.3)
                plt.xticks(rotation=30)
                plt.tight_layout()
                st.pyplot(fig3)

            # Perbandingan tabel terakhir 30 hari
            if not df_global.empty:
                st.subheader("📊 Data Harga 30 Hari Terakhir")
                show = df_global.tail(30)[["Date", "Close", "Close_IDR", "Pct_Change"]].copy()
                show.columns = ["Tanggal", f"Harga ({_cur_global}/ton)", "Harga (IDR/ton)", "Perubahan (%)"]
                def _color_chg(v):
                    try:
                        return "color:green" if float(v) > 0 else ("color:red" if float(v) < 0 else "")
                    except Exception:
                        return ""
                st.dataframe(
                    show.style.map(_color_chg, subset=["Perubahan (%)"]).format({
                        f"Harga ({_cur_global}/ton)": "{:.2f}",
                        "Harga (IDR/ton)":            "Rp {:,.0f}",
                        "Perubahan (%)":              "{:.2f}%",
                    }),
                    use_container_width=True,
                    hide_index=True,
                )

            # =========================================================
            # HARGA CPO PER LITER (IDR)
            # CPO density ≈ 0.891 kg/L → 1 MT = 1000/0.891 ≈ 1122 liter
            # =========================================================
            if not df_global.empty:
                st.divider()
                st.subheader("🫙 Harga CPO Per Liter (Rupiah)")
                st.caption("Konversi: densitas CPO ≈ 0.891 kg/liter → 1 MT ≈ 1.122 liter")

                _LITER_PER_TON = 1000.0 / 0.891   # ≈ 1122 liter/MT

                # --- Global CPO per liter ---
                df_liter = df_global[["Date", "Close_IDR", "Pct_Change"]].copy()
                df_liter["Date"]          = pd.to_datetime(df_liter["Date"])
                df_liter["IDR_per_liter"] = df_liter["Close_IDR"] / _LITER_PER_TON
                n_l = len(df_liter)
                df_liter["MA20_liter"] = df_liter["IDR_per_liter"].rolling(min(20, n_l)).mean()
                df_liter["MA50_liter"] = df_liter["IDR_per_liter"].rolling(min(50, n_l)).mean()

                # --- Indonesia lokal CPO per liter ---
                _src_indo  = ""
                df_liter_id = pd.DataFrame()
                if not df_indo.empty and "Close_IDR" in df_indo.columns:
                    df_liter_id = df_indo[["Date", "Close_IDR"]].copy()
                    df_liter_id["Date"]             = pd.to_datetime(df_liter_id["Date"])
                    df_liter_id["IDR_per_liter_id"] = df_liter_id["Close_IDR"] / _LITER_PER_TON
                    _src_indo = df_indo["Source"].iloc[-1] if "Source" in df_indo.columns else "Lokal ID"

                # ── Metrik baris 1: CPO Global ──
                last_liter    = float(df_liter["IDR_per_liter"].iloc[-1])
                prev_liter    = float(df_liter["IDR_per_liter"].iloc[-2]) if n_l > 1 else last_liter
                chg_liter_pct = ((last_liter - prev_liter) / prev_liter * 100) if prev_liter else 0
                high_liter    = float(df_liter["IDR_per_liter"].tail(252).max())
                low_liter     = float(df_liter["IDR_per_liter"].tail(252).min())

                st.markdown("**🌍 CPO Global (Futures)**")
                cl1, cl2, cl3, cl4 = st.columns(4)
                cl1.metric("Harga/Liter Terkini", f"Rp {last_liter:,.0f}", f"{chg_liter_pct:+.2f}%")
                cl2.metric("Sumber", df_global["Source"].iloc[-1] if "Source" in df_global.columns else "-")
                cl3.metric("52W High/Liter",      f"Rp {high_liter:,.0f}")
                cl4.metric("52W Low/Liter",        f"Rp {low_liter:,.0f}")

                # ── Metrik baris 2: CPO Indonesia ──
                if not df_liter_id.empty:
                    last_id    = float(df_liter_id["IDR_per_liter_id"].iloc[-1])
                    prev_id    = float(df_liter_id["IDR_per_liter_id"].iloc[-2]) if len(df_liter_id) > 1 else last_id
                    chg_id_pct = ((last_id - prev_id) / prev_id * 100) if prev_id else 0
                    high_id    = float(df_liter_id["IDR_per_liter_id"].max())
                    low_id     = float(df_liter_id["IDR_per_liter_id"].min())
                    selisih    = last_id - last_liter

                    st.markdown("**🇮🇩 CPO Indonesia Lokal**")
                    ci1, ci2, ci3, ci4 = st.columns(4)
                    ci1.metric("Harga/Liter Terkini", f"Rp {last_id:,.0f}", f"{chg_id_pct:+.2f}%")
                    ci2.metric("Selisih vs Global",    f"Rp {selisih:+,.0f}",
                               help="Positif = harga lokal lebih mahal dari global")
                    ci3.metric("Tertinggi/Liter",      f"Rp {high_id:,.0f}")
                    ci4.metric("Terendah/Liter",        f"Rp {low_id:,.0f}")
                    if _src_indo:
                        st.caption(f"Sumber: {_src_indo}")

                # ── Grafik perbandingan ──
                fig_l, ax_l = plt.subplots(figsize=(12, 4))

                ax_l.plot(df_liter["Date"], df_liter["IDR_per_liter"],
                          label="CPO Global (IDR/liter)", linewidth=2, color="#9C27B0")
                ax_l.fill_between(df_liter["Date"], df_liter["IDR_per_liter"],
                                  alpha=0.12, color="#9C27B0")

                if not df_liter_id.empty:
                    ax_l.plot(df_liter_id["Date"], df_liter_id["IDR_per_liter_id"],
                              label="CPO Indonesia Lokal (IDR/liter)",
                              linewidth=2, color="#4CAF50", linestyle="-")
                    ax_l.fill_between(df_liter_id["Date"], df_liter_id["IDR_per_liter_id"],
                                      alpha=0.08, color="#4CAF50")

                if df_liter["MA20_liter"].notna().any():
                    ax_l.plot(df_liter["Date"], df_liter["MA20_liter"],
                              label="MA20 (Global)", linestyle="--", color="#FF9800", linewidth=1.2)
                if df_liter["MA50_liter"].notna().any():
                    ax_l.plot(df_liter["Date"], df_liter["MA50_liter"],
                              label="MA50 (Global)", linestyle="--", color="#F44336", linewidth=1.2)

                ax_l.set_title("Perbandingan Harga CPO Global vs Indonesia per Liter (IDR)")
                ax_l.set_ylabel("Rp / liter")
                ax_l.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"Rp {x:,.0f}"))
                ax_l.legend(fontsize=8)
                ax_l.grid(alpha=0.3)
                plt.xticks(rotation=30)
                plt.tight_layout()
                st.pyplot(fig_l)
                plt.close(fig_l)

                # ── Tabel perbandingan ──
                st.markdown("**📋 Tabel Harga CPO / Liter (IDR) — 30 Hari Terakhir**")
                tbl_g = df_liter.tail(30)[["Date", "IDR_per_liter", "Pct_Change"]].copy()
                tbl_g.columns = ["Tanggal", "Global (IDR/liter)", "Perubahan Global (%)"]
                tbl_g["Tanggal"] = tbl_g["Tanggal"].astype(str)

                if not df_liter_id.empty:
                    tbl_id = df_liter_id.tail(30)[["Date", "IDR_per_liter_id"]].copy()
                    tbl_id.columns = ["Tanggal", "Indonesia Lokal (IDR/liter)"]
                    tbl_id["Tanggal"] = tbl_id["Tanggal"].astype(str)
                    tbl_liter = tbl_g.merge(tbl_id, on="Tanggal", how="left")
                else:
                    tbl_liter = tbl_g

                def _color_liter(v):
                    try:
                        return "color:green" if float(v) > 0 else ("color:red" if float(v) < 0 else "")
                    except Exception:
                        return ""

                fmt_tbl = {"Global (IDR/liter)": "Rp {:,.1f}", "Perubahan Global (%)": "{:.2f}%"}
                if "Indonesia Lokal (IDR/liter)" in tbl_liter.columns:
                    fmt_tbl["Indonesia Lokal (IDR/liter)"] = "Rp {:,.1f}"

                st.dataframe(
                    tbl_liter.style.map(_color_liter, subset=["Perubahan Global (%)"]).format(fmt_tbl, na_rep="-"),
                    use_container_width=True,
                    hide_index=True,
                )

    # =========================================================
    # TAB 2 — MINYAK GORENG JAWA TIMUR (SISKAPERBAPO)
    # =========================================================
    with tab_minyak:
        st.markdown("### 🛢️ Harga Minyak Goreng Jawa Timur")
        st.caption("Sumber: SISKAPERBAPO — Sistem Informasi Ketersediaan dan Perkembangan Harga Bahan Pokok Jawa Timur")
        st.divider()

        col_mg1, col_mg2, _ = st.columns([1, 1, 2])
        with col_mg1:
            load_mg = st.button("🔄 Muat Harga Minyak Goreng", use_container_width=True, key="btn_load_mg")
        with col_mg2:
            mg_days = st.selectbox("Periode historis", [7, 14, 21, 30], index=1,
                                   format_func=lambda x: f"{x} hari", key="mg_days")

        if load_mg or st.session_state.get("mg_loaded"):
            if load_mg:
                with st.spinner("Mengambil harga minyak goreng dari SISKAPERBAPO Jatim..."):
                    mg_current  = get_minyakgoreng_current()
                    mg_all_hist = get_minyakgoreng_all_history(days=mg_days)
                _HARI_ID  = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
                _BULAN_ID = ["","Januari","Februari","Maret","April","Mei","Juni",
                             "Juli","Agustus","September","Oktober","November","Desember"]
                _now = datetime.now()
                _ts  = (f"{_HARI_ID[_now.weekday()]}, "
                        f"{_now.day} {_BULAN_ID[_now.month]} {_now.year}  "
                        f"{_now.strftime('%H:%M')} WIB")
                st.session_state["mg_current"]   = mg_current
                st.session_state["mg_all_hist"]  = mg_all_hist
                st.session_state["mg_loaded"]    = True
                st.session_state["mg_loaded_at"] = _ts
            else:
                mg_current  = st.session_state.get("mg_current", {})
                mg_all_hist = st.session_state.get("mg_all_hist", pd.DataFrame())

            # ---- HARGA TERKINI ----
            if mg_current:
                _loaded_at = st.session_state.get("mg_loaded_at", "")
                st.subheader("💰 Harga Terkini (Rata-rata Jawa Timur)")
                if _loaded_at:
                    st.caption(f"🕐 Data diperbarui: **{_loaded_at}**")
                cols_mg = st.columns(len(mg_current))
                for col, (nama, info) in zip(cols_mg, mg_current.items()):
                    harga      = info.get("harga", 0)
                    harga_awal = info.get("harga_awal", harga)
                    chg        = harga - harga_awal
                    chg_pct    = (chg / harga_awal * 100) if harga_awal else 0
                    satuan     = info.get("satuan", "")
                    nama_short = nama.replace("Minyak Goreng ", "").replace(" / liter","").replace(" / kg","")
                    col.metric(
                        label=f"{nama_short}\n({satuan})",
                        value=f"Rp {harga:,.0f}",
                        delta=f"{chg_pct:+.2f}% vs 14 hari lalu"
                    )

                # Bar chart perbandingan harga terkini
                st.divider()
                st.subheader("📊 Perbandingan Harga Semua Jenis")
                mg_bar_data = {
                    k.replace("Minyak Goreng ", ""): v["harga"]
                    for k, v in mg_current.items() if v.get("harga", 0) > 0
                }
                if mg_bar_data:
                    fig_bar, ax_bar = plt.subplots(figsize=(10, 4))
                    _bar_colors = ["#FF6B35", "#F7C59F", "#8BC34A", "#004E89"]
                    bars = ax_bar.bar(
                        list(mg_bar_data.keys()),
                        list(mg_bar_data.values()),
                        color=_bar_colors[:len(mg_bar_data)],
                        edgecolor="white", linewidth=0.8
                    )
                    for bar, val in zip(bars, mg_bar_data.values()):
                        ax_bar.text(bar.get_x() + bar.get_width()/2,
                                    bar.get_height() + 100,
                                    f"Rp {val:,.0f}", ha="center", va="bottom",
                                    fontsize=9, fontweight="bold")
                    ax_bar.set_title("Harga Minyak Goreng Jawa Timur (IDR / kg atau liter)")
                    ax_bar.set_ylabel("Rp")
                    ax_bar.yaxis.set_major_formatter(
                        plt.FuncFormatter(lambda x, _: f"Rp {x:,.0f}")
                    )
                    ax_bar.grid(axis="y", alpha=0.3)
                    plt.xticks(rotation=15, ha="right")
                    plt.tight_layout()
                    st.pyplot(fig_bar)

            # ---- TREND HISTORIS SEMUA 4 JENIS ----
            st.divider()
            st.subheader(f"📈 Trend Harga Semua Jenis Minyak Goreng — {mg_days} Hari Terakhir")
            if mg_all_hist.empty:
                st.warning("Data historis tidak tersedia.")
            else:
                _mg_colors = {
                    "Minyak Goreng Curah":             "#FF6B35",
                    "Minyak Goreng Kemasan Premium":   "#2196F3",
                    "Minyak Goreng Kemasan Sederhana": "#8BC34A",
                    "Minyak Goreng MINYAKITA":         "#9C27B0",
                }

                # ── Grafik Gabungan 4 Jenis ──────────────────────
                fig_all, ax_all = plt.subplots(figsize=(13, 6))
                for jenis, grp in mg_all_hist.groupby("Jenis"):
                    grp   = grp.sort_values("Date").reset_index(drop=True)
                    color = _mg_colors.get(jenis, "#888")
                    label = jenis.replace("Minyak Goreng ", "")

                    # Garis utama + fill
                    ax_all.plot(grp["Date"], grp["Harga"],
                                label=label, linewidth=2.2, color=color,
                                marker="o", markersize=3.5, zorder=3)
                    ax_all.fill_between(grp["Date"], grp["Harga"],
                                        alpha=0.08, color=color)

                    # MA7 tiap jenis (putus-putus)
                    ma7 = grp["Harga"].rolling(min(7, len(grp))).mean()
                    if ma7.notna().any():
                        ax_all.plot(grp["Date"], ma7,
                                    linestyle="--", color=color,
                                    linewidth=1.2, alpha=0.6, zorder=2)

                    # Label harga terakhir di ujung kanan
                    if not grp.empty:
                        last_price = float(grp["Harga"].iloc[-1])
                        last_date  = grp["Date"].iloc[-1]
                        ax_all.annotate(
                            f"Rp {last_price:,.0f}",
                            xy=(last_date, last_price),
                            xytext=(6, 0), textcoords="offset points",
                            fontsize=8, color=color, fontweight="bold",
                            va="center"
                        )

                ax_all.set_title(
                    f"Perbandingan Trend Harga 4 Jenis Minyak Goreng Jawa Timur\n"
                    f"(Sumber: SISKAPERBAPO — {mg_days} Hari Terakhir)",
                    fontsize=11, pad=10
                )
                ax_all.set_ylabel("Rp / kg atau liter")
                ax_all.yaxis.set_major_formatter(
                    plt.FuncFormatter(lambda x, _: f"Rp {x:,.0f}")
                )
                ax_all.legend(loc="upper left", fontsize=9,
                              framealpha=0.85, edgecolor="#ccc")
                ax_all.grid(alpha=0.25, linestyle="--")
                ax_all.set_xlabel("Tanggal")
                plt.xticks(rotation=30)
                plt.tight_layout()
                st.pyplot(fig_all)
                plt.close(fig_all)

                # 4 grafik individual (2x2)
                st.markdown("**📉 Grafik Individual per Jenis**")
                jenis_list = mg_all_hist["Jenis"].unique()
                cols_chart = st.columns(2)
                for i, jenis in enumerate(jenis_list):
                    grp   = mg_all_hist[mg_all_hist["Jenis"] == jenis].sort_values("Date")
                    color = _mg_colors.get(jenis, "#888")
                    label = jenis.replace("Minyak Goreng ", "")
                    with cols_chart[i % 2]:
                        fig_i, ax_i = plt.subplots(figsize=(6, 3))
                        ax_i.plot(grp["Date"], grp["Harga"],
                                  color=color, linewidth=2, marker="o", markersize=3)
                        ax_i.fill_between(grp["Date"], grp["Harga"], alpha=0.15, color=color)
                        # MA7
                        ma7 = grp["Harga"].rolling(min(7, len(grp))).mean()
                        if ma7.notna().any():
                            ax_i.plot(grp["Date"], ma7,
                                      linestyle="--", color="#FF9800", linewidth=1.2, label="MA7")
                        ax_i.set_title(label, fontsize=10)
                        ax_i.set_ylabel("Rp")
                        ax_i.yaxis.set_major_formatter(
                            plt.FuncFormatter(lambda x, _: f"Rp {x:,.0f}")
                        )
                        ax_i.grid(alpha=0.3)
                        plt.xticks(rotation=30, fontsize=7)
                        plt.tight_layout()
                        st.pyplot(fig_i)
                        plt.close(fig_i)

                # Tabel gabungan pivot
                st.divider()
                st.markdown("**📋 Tabel Harga Semua Jenis (IDR)**")
                pivot = mg_all_hist.pivot_table(
                    index="Date", columns="Jenis", values="Harga", aggfunc="mean"
                ).reset_index()
                pivot["Date"] = pivot["Date"].astype(str)
                pivot.columns.name = None
                # Rename kolom agar lebih pendek
                pivot = pivot.rename(columns={c: c.replace("Minyak Goreng ","") for c in pivot.columns})
                fmt_dict = {c: "Rp {:,.0f}" for c in pivot.columns if c != "Date"}
                st.dataframe(
                    pivot.sort_values("Date", ascending=False).style.format(fmt_dict, na_rep="-"),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("Klik **Muat Harga Minyak Goreng** untuk memuat data dari SISKAPERBAPO Jawa Timur.")

    # =========================================================
    # TAB 3 — SENTIMEN BERITA
    # =========================================================
    with tab_sentimen:
        sent_days = st.slider("Rentang berita (hari ke belakang)", 7, 30, 14, key="cpo_sent_days")

        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            load_id = st.button("📰 Berita CPO Indonesia", use_container_width=True)
        with col_btn2:
            load_en = st.button("🌐 Berita CPO Global", use_container_width=True)
        with col_btn3:
            load_mg_news = st.button("🛢️ Berita Minyak Goreng", use_container_width=True)

        if load_id:
            with st.spinner("Mengambil berita CPO Indonesia..."):
                df_news_id = get_cpo_news(sent_days, lang="id")
            st.session_state["cpo_news_id"] = df_news_id

        if load_en:
            with st.spinner("Mengambil berita CPO Global (English)..."):
                df_news_en = get_cpo_news(sent_days, lang="en")
            st.session_state["cpo_news_en"] = df_news_en

        if load_mg_news:
            with st.spinner("Mengambil berita minyak goreng Indonesia..."):
                df_news_mg = get_minyakgoreng_news(sent_days)
            st.session_state["mg_news"] = df_news_mg

        def _render_news_section(df_news, label, flag):
            if df_news is None or df_news.empty:
                st.info(f"Belum ada data berita {label}. Klik tombol muat.")
                return

            st.markdown(f"### {flag} Sentimen Berita CPO {label}")

            # Metrik ringkasan
            pos = (df_news["sentiment_label"] == "Positif").sum()
            neg = (df_news["sentiment_label"] == "Negatif").sum()
            net = (df_news["sentiment_label"] == "Netral").sum()
            total = len(df_news)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Berita", total)
            c2.metric("Positif 🟢", pos)
            c3.metric("Negatif 🔴", neg)
            c4.metric("Netral ⚪", net)

            # Bar chart distribusi
            st.bar_chart(df_news["sentiment_label"].value_counts())

            # WordCloud + Top Kata
            wc, common = get_cpo_wordcloud(df_news)
            col_wc, col_top = st.columns(2)
            with col_wc:
                st.markdown("**☁️ WordCloud**")
                if wc:
                    fig, ax = plt.subplots()
                    ax.imshow(wc); ax.axis("off")
                    st.pyplot(fig)
                else:
                    st.caption("Install `wordcloud` untuk fitur ini.")
            with col_top:
                st.markdown("**📊 Top 10 Kata**")
                if common:
                    st.table(pd.DataFrame(common, columns=["Kata", "Jumlah"]))

            # Top media
            if "media" in df_news.columns and df_news["media"].any():
                st.markdown("**🏆 Media yang Memberitakan**")
                st.bar_chart(df_news["media"].value_counts().head(8))

            # Tren sentimen harian
            if "Date" in df_news.columns:
                df_daily = df_news.groupby("Date")["sentiment_score"].mean().reset_index()
                if not df_daily.empty:
                    st.markdown("**📈 Tren Sentimen Harian**")
                    st.line_chart(df_daily.set_index("Date")["sentiment_score"])

            # Daftar berita
            with st.expander("📰 Lihat Semua Berita"):
                show_cols = [c for c in ["Date", "title", "media", "sentiment_label", "sentiment_score", "keyword"]
                             if c in df_news.columns]
                st.dataframe(df_news[show_cols], use_container_width=True, hide_index=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            _render_news_section(
                st.session_state.get("cpo_news_id"),
                "CPO Indonesia", "🇮🇩"
            )
        with col_s2:
            _render_news_section(
                st.session_state.get("cpo_news_en"),
                "CPO Global", "🌐"
            )

        # ---- Sentimen Minyak Goreng ----
        df_mg_news = st.session_state.get("mg_news")
        if df_mg_news is not None:
            st.divider()
            _render_news_section(df_mg_news, "Minyak Goreng Indonesia", "🛢️")

    # =========================================================
    # TAB 4 — ANALISIS FORECAST
    # =========================================================
    with tab_forecast:
        import plotly.graph_objects as go
        from app.utils.forecast_engine import (
            forecast_gb,
            lag_correlation,
            build_correlation_matrix,
            sentiment_lead_lag,
            build_sentiment_price_df,
            rolling_volatility,
        )

        st.markdown("### 🔮 Analisis Forecast & Statistik CPO")

        # ── PANEL KONFIGURASI ────────────────────────────────────
        _MG_LABELS = {
            "Minyak Goreng Curah": 10,
            "Minyak Goreng Kemasan Premium": 92,
            "Minyak Goreng Kemasan Sederhana": 95,
            "Minyak Goreng MINYAKITA": 96,
        }

        with st.container(border=True):
            st.markdown("#### ⚙️ Pengaturan Analisis")
            cfg_c1, cfg_c2, cfg_c3 = st.columns(3)
            with cfg_c1:
                fc_date_from = st.date_input(
                    "Dari Tanggal",
                    datetime.now() - timedelta(days=365),
                    key="fc_date_from",
                )
            with cfg_c2:
                fc_date_to = st.date_input(
                    "Sampai Tanggal",
                    datetime.now(),
                    key="fc_date_to",
                )
            with cfg_c3:
                fc_mg_type = st.selectbox(
                    "Jenis Minyak Goreng",
                    list(_MG_LABELS.keys()),
                    key="fc_mg_type",
                )

            cfg_c4, cfg_c5 = st.columns(2)
            with cfg_c4:
                fc_horizon = st.slider("Horizon Forecast (hari)", 7, 60, 30, key="fc_horizon")
            with cfg_c5:
                vol_window = st.slider("Rolling window volatilitas (hari)", 10, 60, 30, key="fc_vol_window")

            run_fc = st.button(
                "🚀 Generate Analisis",
                type="primary",
                use_container_width=True,
                key="fc_run",
            )

        # ── AMBIL DATA ───────────────────────────────────────────
        if run_fc:
            _days_diff = max((fc_date_to - fc_date_from).days, 7)
            _yf_period = (
                "3mo" if _days_diff <= 90  else
                "6mo" if _days_diff <= 180 else
                "1y"  if _days_diff <= 365 else
                "2y"  if _days_diff <= 730 else
                "5y"
            )
            _mg_days   = _days_diff
            _news_days = _days_diff

            if _mg_days > 90:
                st.warning(
                    f"⏳ Rentang {_mg_days} hari untuk minyak goreng memerlukan banyak request "
                    f"ke SISKAPERBAPO (~{_mg_days} panggilan API). Proses mungkin lambat."
                )

            _fc_from_str = fc_date_from.strftime("%d/%m/%Y")
            _fc_to_str   = fc_date_to.strftime("%d/%m/%Y")
            with st.spinner(
                f"Mengambil data CPO ({_fc_from_str} – {_fc_to_str}), "
                f"{fc_mg_type} ({_mg_days} hari), "
                f"dan berita CPO ({_news_days} hari)..."
            ):
                _df_cpo_raw = get_cpo_global(_yf_period)
                if not _df_cpo_raw.empty:
                    _df_cpo_raw = _df_cpo_raw[
                        pd.to_datetime(_df_cpo_raw["Date"]) >= pd.Timestamp(fc_date_from)
                    ].reset_index(drop=True)
                _df_mg_raw   = get_minyakgoreng_history(
                    commodity_id=_MG_LABELS[fc_mg_type],
                    days=_mg_days,
                )
                _df_news_raw = get_cpo_news(_news_days, lang="id")

            st.session_state["fc_cpo_data"]  = _df_cpo_raw
            st.session_state["fc_mg_data"]   = _df_mg_raw
            st.session_state["fc_mg_label"]  = fc_mg_type
            st.session_state["fc_news_data"] = _df_news_raw
            st.session_state["fc_loaded"]    = True

        df_global_fc       = st.session_state.get("fc_cpo_data")
        df_mg_fc           = st.session_state.get("fc_mg_data")
        fc_mg_label_loaded = st.session_state.get("fc_mg_label", fc_mg_type)
        df_news_id_fc      = st.session_state.get("fc_news_data")

        if not st.session_state.get("fc_loaded"):
            st.info("⚙️ Atur parameter di atas lalu klik **🚀 Generate Analisis** untuk memulai.")
        elif df_global_fc is None or df_global_fc.empty:
            st.warning("Data CPO tidak berhasil diambil. Periksa koneksi internet.")
        else:
            # ── VISUALISASI 1 — PRICE FORECASTING ────────────────
            st.divider()
            st.markdown("#### 🔮 Visualisasi 1: Price Forecasting")
            st.caption(
                "Prediksi ke depan menggunakan Gradient Boosting + lag features "
                "(tanpa data leakage, CI melebar seiring horizon)."
            )

            with st.spinner("Menghitung forecast harga CPO..."):
                df_fc, ci_base = forecast_gb(
                    df_global_fc["Date"], df_global_fc["Close_IDR"],
                    horizon=fc_horizon, n_lags=14,
                )

            if df_fc.empty:
                st.warning("Data historis terlalu pendek untuk forecast (minimal 29 baris).")
            else:
                fig_fc = go.Figure()

                fig_fc.add_trace(go.Scatter(
                    x=pd.to_datetime(df_global_fc["Date"]),
                    y=df_global_fc["Close_IDR"],
                    name="Historis CPO (IDR/ton)",
                    line=dict(color="#1565C0", width=2),
                ))
                fig_fc.add_trace(go.Scatter(
                    x=pd.concat([df_fc["Date"], df_fc["Date"][::-1]]),
                    y=pd.concat([df_fc["Upper"], df_fc["Lower"][::-1]]),
                    fill="toself",
                    fillcolor="rgba(33,150,243,0.15)",
                    line=dict(color="rgba(0,0,0,0)"),
                    name="Confidence Interval 95%",
                ))
                fig_fc.add_trace(go.Scatter(
                    x=df_fc["Date"],
                    y=df_fc["Forecast"],
                    name=f"Forecast {fc_horizon} hari",
                    line=dict(color="#FF6F00", width=2, dash="dash"),
                ))

                if df_mg_fc is not None and not df_mg_fc.empty and "Harga" in df_mg_fc.columns:
                    fig_fc.add_trace(go.Scatter(
                        x=pd.to_datetime(df_mg_fc["Date"]),
                        y=df_mg_fc["Harga"],
                        name=f"{fc_mg_label_loaded} (IDR/kg)",
                        line=dict(color="#FF6B35", width=1.5),
                        yaxis="y2",
                    ))
                    fig_fc.update_layout(yaxis2=dict(
                        title=f"{fc_mg_label_loaded} (IDR/kg)",
                        overlaying="y", side="right", showgrid=False,
                    ))

                fig_fc.update_layout(
                    title=f"Forecast Harga CPO IDR/ton — Horizon {fc_horizon} Hari",
                    xaxis_title="Tanggal",
                    yaxis_title="Harga CPO (IDR/ton)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    height=480,
                    hovermode="x unified",
                    template="plotly_white",
                )
                st.plotly_chart(fig_fc, use_container_width=True)

                c_ci1, c_ci2, c_ci3 = st.columns(3)
                c_ci1.metric("Forecast Hari +1",             f"Rp {df_fc['Forecast'].iloc[0]:,.0f}")
                c_ci2.metric(f"Forecast Hari +{fc_horizon}", f"Rp {df_fc['Forecast'].iloc[-1]:,.0f}")
                c_ci3.metric("CI Base (±1σ×1.96)",           f"Rp {ci_base:,.0f}")

                with st.expander("📋 Tabel Forecast Lengkap"):
                    st.dataframe(
                        df_fc.assign(
                            Forecast=df_fc["Forecast"].map("Rp {:,.0f}".format),
                            Upper=df_fc["Upper"].map("Rp {:,.0f}".format),
                            Lower=df_fc["Lower"].map("Rp {:,.0f}".format),
                        ),
                        use_container_width=True, hide_index=True,
                    )

            # ── VISUALISASI 2 — CORRELATION & LAG ────────────────
            st.divider()
            st.markdown("#### 📊 Visualisasi 2: Correlation & Lag Analysis")
            st.caption(
                f"Pearson cross-lag antara CPO Global (IDR/ton) dan {fc_mg_label_loaded}. "
                "Lag positif = minyak goreng bereaksi N hari setelah CPO bergerak."
            )

            if df_mg_fc is None or df_mg_fc.empty:
                st.info("Data minyak goreng tidak tersedia untuk periode yang dipilih.")
            else:
                col_corr_a, col_corr_b = st.columns([1, 1])

                with col_corr_a:
                    st.markdown("**Pearson Correlation Matrix**")
                    corr_mat = build_correlation_matrix(
                        df_global_fc, df_mg_fc[["Date", "Harga"]],
                        mg_label=f"{fc_mg_label_loaded} (IDR/kg)",
                    )
                    if not corr_mat.empty:
                        fig_cm, ax_cm = plt.subplots(figsize=(4, 3))
                        im = ax_cm.imshow(corr_mat.values, cmap="RdYlGn", vmin=-1, vmax=1)
                        ax_cm.set_xticks(range(len(corr_mat.columns)))
                        ax_cm.set_yticks(range(len(corr_mat.index)))
                        ax_cm.set_xticklabels(corr_mat.columns, fontsize=7, rotation=20, ha="right")
                        ax_cm.set_yticklabels(corr_mat.index, fontsize=7)
                        for _i in range(len(corr_mat.index)):
                            for _j in range(len(corr_mat.columns)):
                                ax_cm.text(_j, _i, f"{corr_mat.values[_i,_j]:.2f}",
                                           ha="center", va="center", fontsize=9, fontweight="bold")
                        plt.colorbar(im, ax=ax_cm, fraction=0.046, pad=0.04)
                        ax_cm.set_title(f"Korelasi CPO vs {fc_mg_label_loaded}", fontsize=8)
                        plt.tight_layout()
                        st.pyplot(fig_cm)
                        plt.close(fig_cm)
                    else:
                        st.warning("Data tidak cukup untuk korelasi matrix.")

                with col_corr_b:
                    st.markdown("**Cross-Lag Correlation (lag 0–14 hari)**")
                    s1_corr = (df_global_fc
                               .assign(Date=pd.to_datetime(df_global_fc["Date"]))
                               .set_index("Date")["Close_IDR"].sort_index())
                    s2_corr = (df_mg_fc
                               .assign(Date=pd.to_datetime(df_mg_fc["Date"]))
                               .set_index("Date")["Harga"].sort_index())

                    lag_dict = lag_correlation(s1_corr, s2_corr, max_lag=14)
                    if lag_dict:
                        lags   = list(lag_dict.keys())
                        corrs  = list(lag_dict.values())
                        colors = ["#2196F3" if c >= 0 else "#F44336" for c in corrs]

                        fig_lag, ax_lag = plt.subplots(figsize=(5, 3.5))
                        ax_lag.bar(lags, corrs, color=colors)
                        ax_lag.axhline(0, color="black", linewidth=0.8)
                        ax_lag.set_xlabel("Lag (hari)")
                        ax_lag.set_ylabel("Korelasi Pearson")
                        ax_lag.set_title(f"CPO Global → {fc_mg_label_loaded}", fontsize=9)
                        ax_lag.set_xticks(lags)
                        best_lag = max(lag_dict, key=lambda k: abs(lag_dict[k]))
                        ax_lag.annotate(
                            f"Best lag: {best_lag}d\n(r={lag_dict[best_lag]:.2f})",
                            xy=(best_lag, lag_dict[best_lag]),
                            xytext=(best_lag + 1, lag_dict[best_lag] + 0.05),
                            fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.8),
                        )
                        plt.tight_layout()
                        st.pyplot(fig_lag)
                        plt.close(fig_lag)
                    else:
                        st.warning("Data lag tidak cukup.")

            # ── VISUALISASI 3 — SENTIMENT IMPACT ─────────────────
            st.divider()
            st.markdown("#### 📰 Visualisasi 3: Sentiment Impact Analytics")
            st.caption(
                "Korelasi antara sentimen berita hari ini dan perubahan harga CPO N hari ke depan. "
                "Berita diambil otomatis sesuai rentang waktu yang dipilih saat Generate."
            )

            if df_news_id_fc is None or df_news_id_fc.empty:
                st.info("Klik **🚀 Generate Analisis** untuk mengambil data berita sesuai rentang waktu.")
            else:
                col_sent_a, col_sent_b = st.columns([1.4, 1])

                with col_sent_a:
                    st.markdown("**Harga CPO vs Sentimen Harian**")
                    df_sp = build_sentiment_price_df(df_global_fc, df_news_id_fc, price_col="Close_IDR")
                    if not df_sp.empty:
                        fig_sp, ax_sp1 = plt.subplots(figsize=(7, 3.5))
                        ax_sp2 = ax_sp1.twinx()
                        ax_sp1.plot(pd.to_datetime(df_sp["Date"]), df_sp["Close_IDR"],
                                    color="#1565C0", linewidth=2, label="CPO IDR/ton")
                        ax_sp1.set_ylabel("CPO (IDR/ton)", color="#1565C0", fontsize=8)
                        ax_sp1.tick_params(axis="y", labelcolor="#1565C0")
                        ax_sp2.bar(pd.to_datetime(df_sp["Date"]), df_sp["sentiment"],
                                   color="#FF6F00", alpha=0.45, label="Sentimen")
                        ax_sp2.axhline(0, color="gray", linewidth=0.5)
                        ax_sp2.set_ylabel("Sentimen rata-rata", color="#FF6F00", fontsize=8)
                        ax_sp2.tick_params(axis="y", labelcolor="#FF6F00")
                        lines1, labels1 = ax_sp1.get_legend_handles_labels()
                        lines2, labels2 = ax_sp2.get_legend_handles_labels()
                        ax_sp1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")
                        ax_sp1.set_title("Harga CPO vs Sentimen Berita", fontsize=9)
                        plt.xticks(rotation=30, fontsize=7)
                        plt.tight_layout()
                        st.pyplot(fig_sp)
                        plt.close(fig_sp)
                    else:
                        st.warning("Tidak ada tanggal yang beririsan antara harga dan berita.")

                with col_sent_b:
                    st.markdown("**Lead-Lag Sentimen → Harga (+N hari)**")
                    ll_dict = sentiment_lead_lag(
                        df_global_fc, df_news_id_fc, price_col="Close_IDR", max_lag=7
                    )
                    if ll_dict:
                        ll_lags  = list(ll_dict.keys())
                        ll_corrs = list(ll_dict.values())
                        ll_cols  = ["#4CAF50" if c >= 0 else "#F44336" for c in ll_corrs]
                        fig_ll, ax_ll = plt.subplots(figsize=(4.5, 3.5))
                        ax_ll.barh(ll_lags, ll_corrs, color=ll_cols)
                        ax_ll.axvline(0, color="black", linewidth=0.8)
                        ax_ll.set_yticks(ll_lags)
                        ax_ll.set_yticklabels([f"+{l} hari" for l in ll_lags], fontsize=8)
                        ax_ll.set_xlabel("Korelasi Pearson", fontsize=8)
                        ax_ll.set_title("Sentimen hari ini → Harga N hari depan", fontsize=9)
                        plt.tight_layout()
                        st.pyplot(fig_ll)
                        plt.close(fig_ll)
                    else:
                        st.warning("Data tidak cukup untuk analisis lead-lag.")

            # ── VISUALISASI 4 — VOLATILITY & ANOMALY ─────────────
            st.divider()
            st.markdown("#### 📈 Visualisasi 4: Volatility & Anomaly Detection")
            st.caption(
                "Rolling std sebagai ukuran volatilitas. "
                "Titik anomali = |z-score| > 2 (harga menyimpang >2σ dari rata-rata bergerak)."
            )

            series_vol = (df_global_fc
                          .assign(Date=pd.to_datetime(df_global_fc["Date"]))
                          .set_index("Date")["Close_IDR"].sort_index().dropna())

            if len(series_vol) < vol_window:
                st.warning("Data historis terlalu pendek untuk rolling window yang dipilih.")
            else:
                vol, ma, anom = rolling_volatility(series_vol, window=vol_window)

                fig_vol, (ax_v1, ax_v2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True)

                ax_v1.plot(series_vol.index, series_vol.values,
                           color="#1565C0", linewidth=1.5, label="CPO IDR/ton", zorder=2)
                ax_v1.plot(ma.index, ma.values,
                           color="#FF6F00", linewidth=1.5, linestyle="--",
                           label=f"MA{vol_window}", zorder=3)
                if not anom.empty:
                    ax_v1.scatter(anom.index, anom.values,
                                  color="#F44336", s=50, zorder=4,
                                  label=f"Anomali ({len(anom)} titik)")
                ax_v1.set_ylabel("Harga CPO (IDR/ton)", fontsize=9)
                ax_v1.set_title("Harga CPO + Moving Average + Anomali Harga", fontsize=10)
                ax_v1.legend(fontsize=8)
                ax_v1.grid(axis="y", alpha=0.3)

                ax_v2.fill_between(vol.index, vol.values,
                                   color="#9C27B0", alpha=0.35,
                                   label=f"Volatilitas (rolling std {vol_window}d)")
                ax_v2.plot(vol.index, vol.values, color="#9C27B0", linewidth=1.5)
                ax_v2.set_ylabel("Std Deviasi (IDR/ton)", fontsize=9)
                ax_v2.set_xlabel("Tanggal", fontsize=9)
                ax_v2.set_title("Rolling Volatility CPO", fontsize=10)
                ax_v2.legend(fontsize=8)
                ax_v2.grid(axis="y", alpha=0.3)

                plt.xticks(rotation=30, fontsize=7)
                plt.tight_layout()
                st.pyplot(fig_vol)
                plt.close(fig_vol)

                cv1, cv2, cv3, cv4 = st.columns(4)
                cv1.metric("Volatilitas Terkini", f"Rp {vol.dropna().iloc[-1]:,.0f}")
                cv2.metric("Volatilitas Maks",    f"Rp {vol.dropna().max():,.0f}")
                cv3.metric("Volatilitas Min",     f"Rp {vol.dropna().min():,.0f}")
                cv4.metric("Jumlah Anomali",      f"{len(anom)} titik")

                if not anom.empty:
                    with st.expander(f"🔴 Detail {len(anom)} Titik Anomali"):
                        df_anom = anom.reset_index()
                        df_anom.columns = ["Tanggal", "Harga (IDR/ton)"]
                        df_anom["Harga (IDR/ton)"] = df_anom["Harga (IDR/ton)"].map("Rp {:,.0f}".format)
                        st.dataframe(df_anom, use_container_width=True, hide_index=True)


# ==========================================================
# =========== SENTIMENT ANALYSIS + LSTM ====================
# ==========================================================

def render_sentiment_analysis():
    import matplotlib.pyplot as plt

    st.title("💹 Analisis Sentimen & Prediksi LSTM")
    st.caption(
        "Analisis sentimen berita Google News dan pengaruhnya "
        "terhadap volatilitas harga saham."
    )

    # -- status library opsional --
    missing = []
    if not SASTRAWI_OK:    missing.append("PySastrawi")
    if not WORDCLOUD_OK:   missing.append("wordcloud")
    if not TENSORFLOW_OK:  missing.append("tensorflow")
    if missing:
        st.warning(
            f"Library opsional belum terinstall: **{', '.join(missing)}**. "
            "Beberapa fitur dinonaktifkan. Jalankan: "
            f"`pip install {' '.join(missing)}`"
        )

    st.divider()

    # --------------------------------------------------
    # INPUT
    # --------------------------------------------------
    col1, col2 = st.columns(2)
    with col1:
        market  = st.selectbox("Market", ["Indonesia", "Global"])
        ticker  = st.text_input("Ticker", "BBCA")
    with col2:
        source  = st.selectbox("Data Source", ["Yahoo", "Alpha Vantage"])
        keyword_input = st.text_input("Keyword Berita (kosongkan = pakai ticker)")

    kw, suggestions, kw_encoded = smart_keyword(keyword_input, ticker)

    with st.expander("💡 Smart Keyword Suggestions"):
        for s in suggestions:
            st.write(f"• {s}")

    col3, col4 = st.columns(2)
    with col3:
        from datetime import datetime, timedelta
        start = st.date_input("Dari Tanggal", datetime.now() - timedelta(days=30))
    with col4:
        end = st.date_input("Sampai Tanggal", datetime.now())

    if not st.button("🔍 Jalankan Analisis", use_container_width=True):
        return

    is_indo = market == "Indonesia"

    # --------------------------------------------------
    # AMBIL DATA HARGA
    # --------------------------------------------------
    with st.spinner("Mengambil data harga..."):
        df_full  = get_full_history(ticker, is_indo)
        if source == "Yahoo":
            df_range = get_yahoo(ticker, start, end, is_indo)
        else:
            df_range = get_alpha(ticker, start, end)

    if df_full is None or df_range is None:
        st.error("Gagal mengambil data harga. Cek ticker dan koneksi internet.")
        return

    # --------------------------------------------------
    # AMBIL BERITA + SENTIMENT
    # --------------------------------------------------
    with st.spinner("Mengambil berita dari Google News..."):
        df_news, df_daily, wc, common, media = get_news(kw_encoded, start, end)

    if df_daily is not None:
        df_range = pd.merge(df_range, df_daily, on="Date", how="left")

    # --------------------------------------------------
    # TABEL PERIODE
    # --------------------------------------------------
    st.subheader("📊 Tabel Periode")

    cols = ["Date", "Prev_Close", "Close"]
    if not is_indo and "Close_IDR" in df_range.columns:
        cols.append("Close_IDR")
    cols += ["Price_Change", "Pct_Change (%)"]
    if "sentiment_score" in df_range.columns:
        cols += ["sentiment_score", "title"]

    def _color(val):
        if pd.isna(val): return ""
        return "color:green" if val > 0 else "color:red"

    fmt = {
        "Prev_Close":    "{:.2f}",
        "Close":         "{:.2f}",
        "Price_Change":  "{:.2f}",
        "Pct_Change (%)": "{:.2f}",
    }
    if "Close_IDR" in cols:
        fmt["Close_IDR"] = "Rp {:,.0f}"

    st.dataframe(
        df_range[cols].style.map(_color, subset=["Price_Change"]).format(fmt),
        use_container_width=True
    )

    # --------------------------------------------------
    # GRAFIK HARGA
    # --------------------------------------------------
    st.subheader("📈 Grafik Harga Periode")
    st.line_chart(df_range.set_index("Date")["Close"])

    st.subheader("📈 Historis 3 Tahun")
    st.line_chart(df_full.set_index("Date")["Close"])

    # --------------------------------------------------
    # PREDIKSI LSTM
    # --------------------------------------------------
    st.subheader("🤖 Prediksi LSTM")

    if not TENSORFLOW_OK:
        st.info("Install TensorFlow untuk mengaktifkan prediksi LSTM: `pip install tensorflow`")
    else:
        with st.spinner("Melatih model LSTM..."):
            df_pred, err = predict_lstm(df_full)

        if err:
            st.warning(err)
        elif df_pred is not None:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(df_pred["Date"], df_pred["Close"],    label="Actual",   linewidth=2)
            ax.plot(df_pred["Date"], df_pred["Prediksi"], label="Prediksi", linestyle="--")
            ax.legend()
            ax.set_title("Actual vs Prediksi LSTM")
            ax.set_xlabel("Tanggal")
            ax.set_ylabel("Harga")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)

    # --------------------------------------------------
    # WORDCLOUD & TOP KATA
    # --------------------------------------------------
    if df_news is not None:
        col_wc, col_top = st.columns(2)

        with col_wc:
            st.subheader("☁️ WordCloud Berita")
            if wc and WORDCLOUD_OK:
                fig, ax = plt.subplots()
                ax.imshow(wc)
                ax.axis("off")
                st.pyplot(fig)
            else:
                st.info("WordCloud tidak tersedia (install: `pip install wordcloud`)")

        with col_top:
            st.subheader("📊 Top 10 Kata")
            if common:
                st.table(pd.DataFrame(common, columns=["Kata", "Jumlah"]))

        # Top media
        st.subheader("🏆 Top Media")
        if media is not None and not media.empty:
            st.table(media.reset_index().rename(columns={"index": "Media", "media": "Media"}))

        # Sentiment chart
        st.subheader("📊 Distribusi Sentimen")
        st.bar_chart(df_news["sentiment_label"].value_counts())

        # Tabel berita
        st.subheader("📰 Daftar Berita")
        show_cols = ["Date", "title", "media", "sentiment_label", "sentiment_score"]
        st.dataframe(df_news[[c for c in show_cols if c in df_news.columns]],
                     use_container_width=True, hide_index=True)

    # --------------------------------------------------
    # KORELASI SENTIMEN vs HARGA
    # --------------------------------------------------
    if df_range is not None and "sentiment_score" in df_range.columns:
        st.subheader("📊 Korelasi Sentimen vs Perubahan Harga")
        df_corr = df_range[["Date", "Pct_Change (%)", "sentiment_score"]].dropna()

        if len(df_corr) > 2:
            corr = df_corr["Pct_Change (%)"].corr(df_corr["sentiment_score"])
            st.metric("Nilai Korelasi (Pearson)", f"{corr:.4f}")

            if corr > 0.3:
                st.success("📈 Korelasi Positif — sentimen cenderung sejalan dengan kenaikan harga")
            elif corr < -0.3:
                st.error("📉 Korelasi Negatif — sentimen berlawanan arah dengan harga")
            else:
                st.warning("⚖️ Korelasi Lemah — sentimen kurang berpengaruh pada pergerakan harga")

            fig, ax = plt.subplots(figsize=(6, 4))
            ax.scatter(df_corr["sentiment_score"], df_corr["Pct_Change (%)"], alpha=0.7)
            ax.set_xlabel("Sentiment Score")
            ax.set_ylabel("Perubahan Harga (%)")
            ax.set_title("Scatter: Sentimen vs Perubahan Harga")
            ax.axhline(0, color="gray", linewidth=0.5)
            ax.axvline(0, color="gray", linewidth=0.5)
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.warning("Data tidak cukup untuk menghitung korelasi.")

    # --------------------------------------------------
    # REKOMENDASI TRADING
    # --------------------------------------------------
    st.subheader("💡 Rekomendasi Trading")

    if df_range is not None and "sentiment_score" in df_range.columns:
        rec_today, rec_tomorrow = generate_recommendation(df_range)

        col_a, col_b = st.columns(2)

        def _rec_box(col, label, rec):
            with col:
                if rec == "BELI":
                    col.success(f"**{label}:** ✅ {rec}")
                elif rec == "JANGAN BELI":
                    col.error(f"**{label}:** ❌ {rec}")
                else:
                    col.warning(f"**{label}:** 👀 {rec}")

        _rec_box(col_a, "📅 Hari Ini", rec_today)
        _rec_box(col_b, "📅 Besok (Estimasi)", rec_tomorrow)

        st.caption(
            "⚠️ Rekomendasi ini bersifat indikatif berdasarkan sentimen berita dan tren "
            "harga 3 hari terakhir — bukan saran investasi."
        )
    else:
        st.info("Ambil data berita terlebih dahulu untuk melihat rekomendasi.")


# ==========================================================
# =================== KALKULATOR SAHAM =====================
# ==========================================================

def render_kalkulator_saham():

    st.header("🧮 Kalkulator Saham")
    st.caption("Alat bantu hitung untuk keputusan investasi yang lebih akurat.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Average Saham",
        "📄 Rights Issue",
        "📉 Recovery",
        "💸 Dividen",
        "💼 Alokasi Dana",
    ])

    # ──────────────────────────────────────────────────────────
    # TAB 1 — KALKULATOR AVERAGE SAHAM
    # ──────────────────────────────────────────────────────────
    with tab1:

        col_input, col_result = st.columns([1, 1], gap="large")

        # ── KOLOM KIRI: INPUT ─────────────────────────────────
        with col_input:
            st.markdown(
                """
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                  <span style="font-size:28px;">📋</span>
                  <div>
                    <div style="font-size:18px;font-weight:700;">Kalkulator Average Saham</div>
                    <div style="font-size:12px;color:#9ca3af;">
                      Hitung harga rata-rata baru setelah membeli saham tambahan secara akurat.
                    </div>
                  </div>
                </div>
                <hr style="margin:10px 0 16px 0;">
                """,
                unsafe_allow_html=True,
            )

            # POSISI SAAT INI
            st.markdown(
                "<p style='font-size:11px;font-weight:700;color:#6b7280;"
                "letter-spacing:1px;margin-bottom:6px;'>POSISI SAAT INI</p>",
                unsafe_allow_html=True,
            )

            ca1, ca2 = st.columns(2)
            with ca1:
                st.caption("LOT DIMILIKI")
                avg_lot_awal = st.number_input(
                    "lot_dimiliki", min_value=0, value=0, step=1,
                    key="avg_lot_awal", label_visibility="collapsed",
                    placeholder="Contoh: 10",
                )
            with ca2:
                st.caption("HARGA RATA-RATA (AVG)")
                avg_harga_awal = st.number_input(
                    "harga_avg", min_value=0, value=0, step=1,
                    key="avg_harga_awal", label_visibility="collapsed",
                    placeholder="Contoh: 5500",
                )

            total_posisi_auto = avg_lot_awal * 100 * avg_harga_awal

            ca3, ca4 = st.columns(2)
            with ca3:
                st.caption("TOTAL POSISI (AUTO)")
                st.markdown(
                    f"<div style='border:1px solid #374151;border-radius:8px;"
                    f"padding:8px 12px;font-size:14px;color:#d1fae5;min-height:40px;'>"
                    f"{'Rp ' + f'{int(total_posisi_auto):,}'.replace(',','.') if total_posisi_auto else '—'}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

            # RENCANA PEMBELIAN
            st.markdown(
                "<p style='font-size:11px;font-weight:700;color:#6b7280;"
                "letter-spacing:1px;margin-bottom:6px;'>RENCANA PEMBELIAN</p>",
                unsafe_allow_html=True,
            )

            cb1, cb2 = st.columns(2)
            with cb1:
                st.caption("LOT AKAN DIBELI")
                avg_lot_baru = st.number_input(
                    "lot_baru", min_value=0, value=0, step=1,
                    key="avg_lot_baru", label_visibility="collapsed",
                    placeholder="Contoh: 5",
                )
            with cb2:
                st.caption("HARGA BELI")
                avg_harga_baru = st.number_input(
                    "harga_baru", min_value=0, value=0, step=1,
                    key="avg_harga_baru", label_visibility="collapsed",
                    placeholder="Contoh: 5000",
                )

            total_beli_auto = avg_lot_baru * 100 * avg_harga_baru

            cb3, cb4 = st.columns(2)
            with cb3:
                st.caption("TOTAL BELI (AUTO)")
                st.markdown(
                    f"<div style='border:1px solid #374151;border-radius:8px;"
                    f"padding:8px 12px;font-size:14px;color:#d1fae5;min-height:40px;'>"
                    f"{'Rp ' + f'{int(total_beli_auto):,}'.replace(',','.') if total_beli_auto else '—'}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

            # TOMBOL
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("↺ Reset", key="avg_reset", use_container_width=True):
                    for k in ["avg_lot_awal", "avg_harga_awal", "avg_lot_baru", "avg_harga_baru"]:
                        st.session_state[k] = 0
                    st.rerun()
            with btn_col2:
                # Bagikan: tampilkan summary di clipboard-style
                if st.button("⟵ Bagikan", key="avg_share", use_container_width=True, type="primary"):
                    st.session_state["avg_share_show"] = True

        # ── KOLOM KANAN: HASIL ────────────────────────────────
        with col_result:

            # Hitung
            modal_awal  = avg_lot_awal  * 100 * avg_harga_awal
            modal_baru  = avg_lot_baru  * 100 * avg_harga_baru
            total_lot   = avg_lot_awal  + avg_lot_baru
            total_saham = total_lot     * 100
            total_modal = modal_awal    + modal_baru
            harga_avg_baru = (total_modal / total_saham) if total_saham > 0 else 0

            pct_change = (
                (harga_avg_baru - avg_harga_awal) / avg_harga_awal * 100
                if avg_harga_awal > 0 else 0
            )

            st.markdown(
                """
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
                  <span style="font-size:20px;">📊</span>
                  <span style="font-size:15px;font-weight:700;letter-spacing:1px;">
                    HASIL KALKULASI
                  </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            def _result_card(label, value, highlight=False):
                bg    = "#1a3a2a" if highlight else "#1f2937"
                border = "#22c55e" if highlight else "#374151"
                vcolor = "#4ade80" if highlight else "#f1f5f9"
                lcolor = "#86efac" if highlight else "#9ca3af"
                fsize  = "22px"   if highlight else "18px"
                st.markdown(
                    f"""
                    <div style="background:{bg};border:1px solid {border};
                                border-radius:10px;padding:14px 16px;margin-bottom:12px;">
                      <div style="font-size:10px;font-weight:700;color:{lcolor};
                                  letter-spacing:1px;margin-bottom:6px;">{label}</div>
                      <div style="font-size:{fsize};font-weight:700;color:{vcolor};">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            _result_card(
                "TOTAL ASET BARU",
                f"Rp {int(total_modal):,}".replace(",", ".") if total_modal else "—",
            )
            _result_card(
                "TOTAL LOT DIMILIKI",
                f"{total_lot} lot" if total_lot else "—",
            )
            _result_card(
                "HARGA RATA-RATA BARU",
                f"Rp {int(harga_avg_baru):,}".replace(",", ".") if harga_avg_baru else "—",
                highlight=True,
            )

            if harga_avg_baru and avg_harga_awal:
                if pct_change < 0:
                    st.success(f"✅ Average turun {abs(pct_change):.2f}% dari harga awal")
                elif pct_change > 0:
                    st.warning(f"⚠️ Average naik {pct_change:.2f}% dari harga awal")
                else:
                    st.info("➡️ Average tidak berubah")

            st.markdown(
                "<p style='font-size:11px;color:#6b7280;margin-top:8px;'>"
                "*Simulasi tidak termasuk biaya broker.</p>",
                unsafe_allow_html=True,
            )

        # BAGIKAN
        if st.session_state.get("avg_share_show") and harga_avg_baru:
            share_text = (
                f"📋 Average Saham\n"
                f"Lot Lama: {avg_lot_awal} lot @ Rp {avg_harga_awal:,}\n"
                f"Lot Baru: {avg_lot_baru} lot @ Rp {avg_harga_baru:,}\n"
                f"→ Harga Rata-rata Baru: Rp {int(harga_avg_baru):,}\n"
                f"→ Total Lot: {total_lot} lot\n"
                f"→ Total Modal: Rp {int(total_modal):,}"
            ).replace(",", ".")
            st.code(share_text, language=None)
            st.session_state["avg_share_show"] = False

    # ──────────────────────────────────────────────────────────
    # TAB 2 — KALKULATOR RIGHTS ISSUE
    # ──────────────────────────────────────────────────────────
    with tab2:
        st.subheader("📄 Kalkulator Rights Issue")
        st.caption(
            "Hitung HMETD, harga teoritis, dan potensi profit setelah menebus rights issue."
        )
        st.markdown("---")

        c1, c2 = st.columns(2)

        with c1:
            ri_saham_dimiliki  = st.number_input("Saham yang dimiliki (lembar)", min_value=100, value=10000, step=100, key="ri_saham")
            ri_rasio_old       = st.number_input("Rasio lama (A saham lama)", min_value=1, value=5, key="ri_rasio_old",
                                                  help="Contoh: rasio 5:3 → A=5")
            ri_rasio_new       = st.number_input("Rasio baru (B saham baru)", min_value=1, value=3, key="ri_rasio_new",
                                                  help="Contoh: rasio 5:3 → B=3")
            ri_harga_pasar     = st.number_input("Harga pasar saat ini (Rp)", min_value=1, value=500, step=1, key="ri_harga_pasar")

        with c2:
            ri_harga_pelaksanaan = st.number_input("Harga pelaksanaan / exercise price (Rp)", min_value=1, value=300, step=1, key="ri_ex")
            ri_nilai_hmetd       = st.number_input("Nilai HMETD per rights (Rp, 0=hitung otomatis)", min_value=0, value=0, step=1, key="ri_hmetd_val")

        if st.button("Hitung Rights Issue", key="btn_ri", use_container_width=True, type="primary"):
            hmetd_diterima = int(ri_saham_dimiliki / ri_rasio_old * ri_rasio_new)

            # Harga teoritis ex-rights (TERP)
            total_saham_setelah = ri_saham_dimiliki + hmetd_diterima
            total_nilai_setelah = (ri_saham_dimiliki * ri_harga_pasar) + (hmetd_diterima * ri_harga_pelaksanaan)
            harga_teoritis = total_nilai_setelah / total_saham_setelah

            # Nilai HMETD
            if ri_nilai_hmetd > 0:
                nilai_hmetd_per_rights = ri_nilai_hmetd
            else:
                nilai_hmetd_per_rights = max(0, harga_teoritis - ri_harga_pelaksanaan)

            total_nilai_hmetd = hmetd_diterima * nilai_hmetd_per_rights

            # P&L jika ditebus
            biaya_tebus = hmetd_diterima * ri_harga_pelaksanaan
            nilai_saham_baru = hmetd_diterima * harga_teoritis
            profit_tebus = nilai_saham_baru - biaya_tebus

            st.markdown("---")
            st.markdown("#### Hasil")

            c1r, c2r, c3r = st.columns(3)
            c1r.metric("HMETD Diterima", f"{hmetd_diterima:,} rights".replace(",", "."))
            c2r.metric("Harga Teoritis (TERP)", f"Rp {harga_teoritis:,.0f}".replace(",", "."))
            c3r.metric("Nilai HMETD Total", f"Rp {int(total_nilai_hmetd):,}".replace(",", "."))

            c4r, c5r, _ = st.columns(3)
            c4r.metric("Biaya Tebus", f"Rp {int(biaya_tebus):,}".replace(",", "."))
            c5r.metric(
                "Potensi Profit (Tebus)",
                f"Rp {int(profit_tebus):,}".replace(",", "."),
                delta="Untung" if profit_tebus >= 0 else "Rugi",
                delta_color="normal" if profit_tebus >= 0 else "inverse",
            )

            if profit_tebus > 0:
                st.success(f"✅ Jika ditebus: potensi untung Rp {int(profit_tebus):,}".replace(",", "."))
            else:
                st.warning(f"⚠️ Harga pelaksanaan di atas TERP — pertimbangkan jual HMETD di pasar")

    # ──────────────────────────────────────────────────────────
    # TAB 3 — KALKULATOR RECOVERY
    # ──────────────────────────────────────────────────────────
    with tab3:

        import pandas as pd

        st.subheader("📉 Kalkulator Recovery")
        st.caption("Hitung gain yang dibutuhkan untuk balik modal & berapa nominal average down.")
        st.markdown("---")

        # ── INPUT ─────────────────────────────────────────────
        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            rec_harga_beli     = st.number_input(
                "Harga beli rata-rata (Rp)",
                min_value=1, value=1000, step=1, key="rec_beli"
            )
        with ci2:
            rec_lot            = st.number_input(
                "Jumlah lot dimiliki",
                min_value=1, value=10, key="rec_lot"
            )
        with ci3:
            rec_harga_sekarang = st.number_input(
                "Harga sekarang (Rp)",
                min_value=1, value=850, step=1, key="rec_sekarang"
            )

        # ── KALKULASI DASAR ───────────────────────────────────
        modal          = rec_harga_beli * rec_lot * 100
        nilai_skrg     = rec_harga_sekarang * rec_lot * 100
        rugi_nominal   = nilai_skrg - modal
        rugi_pct       = (rugi_nominal / modal) * 100
        gain_needed    = (rec_harga_beli - rec_harga_sekarang) / rec_harga_sekarang * 100

        # ── METRICS ──────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Modal Awal",    f"Rp {int(modal):,}".replace(",", "."))
        m2.metric("Nilai Saat Ini", f"Rp {int(nilai_skrg):,}".replace(",", "."))
        m3.metric(
            "Floating Loss",
            f"Rp {abs(int(rugi_nominal)):,}".replace(",", "."),
            delta=f"{rugi_pct:.2f}%",
            delta_color="inverse" if rugi_pct < 0 else "normal",
        )
        m4.metric(
            "Gain untuk Balik Modal",
            f"{gain_needed:.2f}%" if rugi_pct < 0 else "0%",
            delta="dari harga sekarang" if rugi_pct < 0 else "Sudah profit",
            delta_color="off",
        )

        if rugi_pct >= 0:
            st.success("✅ Posisi sedang profit atau break even")
        else:
            st.error(
                f"📌 Harga perlu naik **{gain_needed:.2f}%** "
                f"dari Rp {rec_harga_sekarang:,} → Rp {rec_harga_beli:,}".replace(",", ".")
            )

        # ── NOMINAL UNTUK AVERAGE = HARGA SEKARANG ───────────
        st.markdown("---")
        st.markdown("#### 🎯 Berapa Nominal untuk Average Turun ke Target?")
        st.caption(
            "Hitung berapa uang yang harus dibeli **di harga sekarang** "
            "agar average kamu turun ke harga target yang diinginkan."
        )

        # Input target average
        target_default = max(rec_harga_sekarang + 1, int((rec_harga_beli + rec_harga_sekarang) / 2))
        rec_target_avg = st.number_input(
            "Target Average yang Diinginkan (Rp)",
            min_value=rec_harga_sekarang + 1,
            max_value=rec_harga_beli,
            value=min(target_default, rec_harga_beli),
            step=1,
            key="rec_target_avg",
            help=(
                f"Harus di antara harga sekarang (Rp {rec_harga_sekarang:,}) "
                f"dan harga beli (Rp {rec_harga_beli:,}). "
                f"Makin mendekati harga sekarang → makin banyak modal dibutuhkan."
            ).replace(",", "."),
        )

        if rec_harga_sekarang < rec_harga_beli:
            selisih_target = rec_target_avg - rec_harga_sekarang
            if selisih_target > 0:
                lot_dibutuhkan  = rec_lot * (rec_harga_beli - rec_target_avg) / selisih_target
                lot_dibutuhkan  = max(0, lot_dibutuhkan)
                nominal_dibutuhkan = lot_dibutuhkan * 100 * rec_harga_sekarang

                total_lot_stlh  = rec_lot + lot_dibutuhkan
                total_modal_stlh = modal + nominal_dibutuhkan
                avg_check       = total_modal_stlh / (total_lot_stlh * 100)
                gain_stlh       = (avg_check - rec_harga_sekarang) / rec_harga_sekarang * 100
                hemat_gain      = gain_needed - gain_stlh

                # ── HASIL UTAMA ─────────────────────────────
                ha, hb, hc = st.columns(3)
                ha.metric(
                    "💰 Nominal yang Harus Dibeli",
                    f"Rp {int(nominal_dibutuhkan):,}".replace(",", "."),
                )
                hb.metric(
                    "📦 Lot yang Harus Dibeli",
                    f"± {int(lot_dibutuhkan):,} lot".replace(",", "."),
                )
                hc.metric(
                    "📈 Gain Dibutuhkan Setelah Average Down",
                    f"{gain_stlh:.2f}%",
                    delta=f"hemat {hemat_gain:.2f}% vs sekarang",
                    delta_color="normal",
                )

                # Info box
                st.info(
                    f"Dengan membeli **{int(lot_dibutuhkan):,} lot** "
                    f"senilai **Rp {int(nominal_dibutuhkan):,}** "
                    f"di harga Rp {rec_harga_sekarang:,}, "
                    f"average kamu turun ke sekitar **Rp {int(avg_check):,}** "
                    f"(target: Rp {int(rec_target_avg):,}).\n\n"
                    f"Kamu hanya perlu gain **{gain_stlh:.2f}%** untuk break even "
                    f"(hemat {hemat_gain:.2f}% dibanding tanpa average down)."
                    .replace(",", ".")
                )

        # ── TABEL SKENARIO TARGET AVERAGE ─────────────────────
        st.markdown("---")
        st.markdown("**Tabel Skenario: Nominal per Target Average**")
        st.caption("Semakin rendah target average → semakin besar nominal yang harus dibeli.")

        if rec_harga_sekarang < rec_harga_beli:
            gap = rec_harga_beli - rec_harga_sekarang
            targets = [
                int(rec_harga_beli - gap * pct / 100)
                for pct in [20, 40, 60, 80, 95]
            ]
            targets = [t for t in targets if t > rec_harga_sekarang]

            rows_t = []
            for tgt in targets:
                sel = tgt - rec_harga_sekarang
                if sel <= 0:
                    continue
                lt  = rec_lot * (rec_harga_beli - tgt) / sel
                nom = lt * 100 * rec_harga_sekarang
                ttl = rec_lot + lt
                avg_t = (modal + nom) / (ttl * 100)
                g_t   = (avg_t - rec_harga_sekarang) / rec_harga_sekarang * 100
                rows_t.append({
                    "Target Average": f"Rp {int(tgt):,}".replace(",", "."),
                    "Turun dari Beli": f"-{int(rec_harga_beli - tgt):,}".replace(",", "."),
                    "Lot Harus Dibeli": f"{int(lt):,} lot".replace(",", "."),
                    "Nominal Harus Dibeli": f"Rp {int(nom):,}".replace(",", "."),
                    "Gain Dibutuhkan": f"{g_t:.2f}%",
                })

            if rows_t:
                st.dataframe(
                    pd.DataFrame(rows_t),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    "💡 Catatan: Average tidak bisa sama persis dengan harga sekarang karena secara "
                    "matematis membutuhkan modal tak terbatas. Target minimum = harga sekarang + 1."
                )
        else:
            st.success("✅ Tidak perlu average down — posisi sudah profit atau break even.")

    # ──────────────────────────────────────────────────────────
    # TAB 4 — KALKULATOR DIVIDEN (SNOWBALL)
    # ──────────────────────────────────────────────────────────
    with tab4:
        st.subheader("💸 Kalkulator Dividen (Snowball Effect)")
        st.caption(
            "Simulasi snowball effect dividen dan hitung kapan dividen bisa beli lot otomatis."
        )
        st.markdown("---")

        c1, c2 = st.columns(2)

        with c1:
            div_lot_awal       = st.number_input("Lot awal yang dimiliki", min_value=1, value=10, key="div_lot")
            div_harga          = st.number_input("Harga saham saat ini (Rp)", min_value=1, value=1000, step=1, key="div_harga")
            div_per_saham      = st.number_input("Dividen per saham per tahun (Rp)", min_value=1, value=50, step=1, key="div_per_saham")

        with c2:
            div_pajak          = st.number_input("Pajak dividen (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.5, key="div_pajak")
            div_tahun          = st.slider("Simulasi (tahun)", min_value=1, max_value=30, value=10, key="div_tahun")
            div_reinvest       = st.checkbox("Reinvest dividen (beli lot baru)", value=True, key="div_reinvest")

        if st.button("Hitung Snowball", key="btn_div", use_container_width=True, type="primary"):
            import pandas as pd
            import plotly.graph_objects as go

            rows = []
            lot_sekarang   = div_lot_awal
            total_dividen  = 0.0
            sisa_kas       = 0.0

            for tahun in range(1, div_tahun + 1):
                saham_dimiliki = lot_sekarang * 100
                dividen_kotor  = saham_dimiliki * div_per_saham
                pajak          = dividen_kotor * (div_pajak / 100)
                dividen_bersih = dividen_kotor - pajak

                lot_beli_baru = 0
                if div_reinvest:
                    sisa_kas      += dividen_bersih
                    biaya_per_lot  = div_harga * 100
                    lot_beli_baru  = int(sisa_kas // biaya_per_lot)
                    sisa_kas      -= lot_beli_baru * biaya_per_lot
                    lot_sekarang  += lot_beli_baru

                total_dividen += dividen_bersih

                rows.append({
                    "Tahun":            tahun,
                    "Lot Dimiliki":     lot_sekarang,
                    "Saham (lembar)":   lot_sekarang * 100,
                    "Dividen Kotor":    f"Rp {int(dividen_kotor):,}".replace(",", "."),
                    "Pajak":            f"Rp {int(pajak):,}".replace(",", "."),
                    "Dividen Bersih":   f"Rp {int(dividen_bersih):,}".replace(",", "."),
                    "Lot Beli Baru":    lot_beli_baru,
                    "Sisa Kas":         f"Rp {int(sisa_kas):,}".replace(",", "."),
                })

            st.markdown("---")
            st.markdown("#### Hasil Simulasi")

            c1r, c2r, c3r = st.columns(3)
            c1r.metric("Total Dividen Bersih", f"Rp {int(total_dividen):,}".replace(",", "."))
            c2r.metric("Lot Akhir", f"{lot_sekarang} lot")
            c3r.metric("Pertumbuhan Lot",
                       f"+{lot_sekarang - div_lot_awal} lot",
                       delta=f"{(lot_sekarang - div_lot_awal) / div_lot_awal * 100:.1f}%")

            df_sim = pd.DataFrame(rows)
            st.dataframe(df_sim, use_container_width=True, hide_index=True)

            # Grafik pertumbuhan lot
            fig_div = go.Figure()
            fig_div.add_trace(go.Scatter(
                x=df_sim["Tahun"],
                y=df_sim["Lot Dimiliki"],
                mode="lines+markers",
                name="Total Lot",
                line=dict(color="#22c55e", width=2.5),
                fill="tozeroy",
                fillcolor="rgba(34,197,94,0.12)",
                hovertemplate="Tahun %{x}<br>Lot: %{y}<extra></extra>",
            ))
            fig_div.update_layout(
                xaxis_title="Tahun",
                yaxis_title="Lot Dimiliki",
                height=300,
                margin=dict(l=10, r=10, t=10, b=40),
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font=dict(color="#f1f5f9"),
            )
            st.plotly_chart(fig_div, use_container_width=True)

            # Kapan bisa beli lot pertama dari dividen
            first_buy = next(
                (r for r in rows if r["Lot Beli Baru"] > 0), None
            )
            if first_buy:
                st.success(
                    f"🎯 Pertama kali beli lot baru dari dividen: **Tahun {first_buy['Tahun']}** "
                    f"({first_buy['Lot Beli Baru']} lot)"
                )
            elif not div_reinvest:
                st.info("ℹ️ Aktifkan 'Reinvest dividen' untuk simulasi beli lot otomatis.")
            else:
                st.warning(
                    "⚠️ Dalam periode simulasi ini dividen belum cukup untuk beli 1 lot. "
                    "Coba tambah jumlah lot awal atau perpanjang periode."
                )

    # ──────────────────────────────────────────────────────────
    # TAB 5 — KALKULATOR ALOKASI DANA
    # ──────────────────────────────────────────────────────────
    with tab5:
        st.subheader("💼 Kalkulator Alokasi Dana")
        st.caption(
            "Simulasikan pembagian modal ke tiap strategi investasi secara proporsional."
        )
        st.markdown("---")

        total_modal_alloc = st.number_input(
            "Total Modal yang Tersedia (Rp)",
            min_value=0,
            value=10_000_000,
            step=500_000,
            key="alloc_modal",
            format="%d",
        )

        st.markdown("**Masukkan Strategi dan Persentase Alokasi**")
        st.caption("Total harus = 100%. Kosongkan nama strategi jika tidak digunakan.")

        STRATEGIES = [
            ("Swing Trade / Aktif", 40),
            ("Dividen / Hold Jangka Panjang", 30),
            ("Cash / Emergency Reserve", 20),
            ("Speculative / ARA Hunter", 10),
        ]

        alloc_data = []
        total_pct = 0.0

        cols_strat = st.columns([3, 1])
        for i, (default_name, default_pct) in enumerate(STRATEGIES):
            c_name, c_pct = st.columns([3, 1])
            with c_name:
                name = st.text_input(
                    f"Strategi {i+1}",
                    value=default_name,
                    key=f"alloc_name_{i}",
                    label_visibility="collapsed",
                )
            with c_pct:
                pct = st.number_input(
                    f"% {i+1}",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default_pct),
                    step=1.0,
                    key=f"alloc_pct_{i}",
                    label_visibility="collapsed",
                )
            if name.strip():
                alloc_data.append((name.strip(), pct))
                total_pct += pct

        if st.button("Hitung Alokasi", key="btn_alloc", use_container_width=True, type="primary"):
            st.markdown("---")
            st.markdown("#### Hasil Alokasi")

            if abs(total_pct - 100) > 0.01:
                st.warning(f"⚠️ Total persentase = {total_pct:.1f}% (harus 100%)")

            import pandas as pd
            import plotly.graph_objects as go

            rows_alloc = []
            for name, pct in alloc_data:
                if pct <= 0:
                    continue
                nominal = total_modal_alloc * pct / 100
                rows_alloc.append({
                    "Strategi":   name,
                    "Alokasi (%)": f"{pct:.1f}%",
                    "Nominal (Rp)": f"Rp {int(nominal):,}".replace(",", "."),
                })

            if rows_alloc:
                st.dataframe(
                    pd.DataFrame(rows_alloc),
                    use_container_width=True,
                    hide_index=True,
                )

                # Pie chart
                fig_pie = go.Figure(go.Pie(
                    labels=[r["Strategi"] for r in rows_alloc],
                    values=[alloc_data[i][1] for i, _ in enumerate(rows_alloc)],
                    hole=0.4,
                    marker=dict(colors=[
                        "#22c55e", "#60a5fa", "#fbbf24", "#ef4444",
                        "#a78bfa", "#fb923c", "#34d399", "#f472b6"
                    ][:len(rows_alloc)]),
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>%{percent}<extra></extra>",
                ))
                fig_pie.update_layout(
                    height=350,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="#0e1117",
                    font=dict(color="#f1f5f9"),
                    showlegend=False,
                )
                st.plotly_chart(fig_pie, use_container_width=True)

                total_nominal = sum(
                    total_modal_alloc * pct / 100
                    for _, pct in alloc_data
                    if pct > 0
                )
                st.caption(
                    f"Total dialokasikan: Rp {int(total_nominal):,}".replace(",", ".")
                    + f" ({total_pct:.1f}% dari modal)"
                )


# ==========================================================
# ======================= ROUTER ===========================
# ==========================================================
menu = st.sidebar.radio(
    "📂 Menu",
    [
        "🔍 Screener",
        "🧠 Multi-Algo Screener",
        "📊 Stock Analysis",
        "🧮 Kalkulator Saham",
        "💰 Dividend Screener",
        "📘 Strategy Guide",
        "📒 Trading Tracker - Summary",
        "⚙️ Trading Tracker - Manage",
        "🌿 Harga CPO dan Minyak Goreng",
    ]
)

if menu == "🔍 Screener":
    render_screener()

elif menu == "🧠 Multi-Algo Screener":
    render_multi_algo_screener()

elif menu == "📊 Stock Analysis":
    render_stock_analysis()

elif menu == "🧮 Kalkulator Saham":
    render_kalkulator_saham()

elif menu == "🌿 Harga CPO dan Minyak Goreng":
    render_cpo_monitor()

elif menu == "💰 Dividend Screener":
    render_dividend_screener()

elif menu == "📘 Strategy Guide":
    render_strategy_guide()

elif menu == "📒 Trading Tracker - Summary":
    render_trading_summary()

elif menu == "⚙️ Trading Tracker - Manage":
    render_manage_data()

# ==========================================================
# FOOTER
# ==========================================================

import os

QRIS_PATH = os.path.join(
    ROOT_DIR,
    "assets",
    "qris.png"
)

st.markdown("---")

col1, col2 = st.columns([3, 1])

with col1:

    st.caption(
        "© 2026 Cuanmology • AI-Powered Stock Screener"
    )

with col2:

    with st.popover("🏠 Help Me Buy a House"):

        st.markdown(
        """### 🏠 Help Me Buy a House


        """
        )

        st.image(
            QRIS_PATH,
            width=310
        )

        st.caption(
            "Scan QRIS via mobile banking / e-wallet"
        )