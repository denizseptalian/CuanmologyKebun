"""
CPO Monitor Engine
Sumber data:
  Global  : CPO=F (NYMEX futures, USD/MT) via yfinance
  Kurs    : open.er-api.com (gratis, tanpa API key)
  Lokal ID: KPBN scraping → fallback estimasi dari CPO=F * kurs USD/IDR
  Berita  : Google News RSS via feedparser
"""

import os
import re
import urllib.parse
from datetime import datetime, timedelta
from collections import Counter

import numpy as np
import pandas as pd
import requests

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_OK = True
except ImportError:
    CURL_CFFI_OK = False

try:
    import feedparser
    FEEDPARSER_OK = True
except ImportError:
    FEEDPARSER_OK = False

try:
    import yfinance as yf
    YFINANCE_OK = True
except ImportError:
    YFINANCE_OK = False

try:
    from wordcloud import WordCloud
    WORDCLOUD_OK = True
except ImportError:
    WORDCLOUD_OK = False

try:
    from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
    _sw = StopWordRemoverFactory().create_stop_word_remover()
    SASTRAWI_OK = True
except ImportError:
    SASTRAWI_OK = False
    _sw = None

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _http_get(url: str, timeout: int = 8):
    """
    HTTP GET dengan fallback: curl_cffi (impersonate Chrome) → requests biasa.
    curl_cffi bisa bypass Cloudflare / geo-block yang memblokir requests standar.
    """
    if CURL_CFFI_OK:
        try:
            return curl_requests.get(url, impersonate="chrome110", timeout=timeout)
        except Exception:
            pass
    return requests.get(url, headers=HEADERS, timeout=timeout)

# ============================================================
# KURS IDR — open.er-api.com (gratis, tanpa API key)
# ============================================================

_kurs_cache: dict = {}

def get_kurs_idr(base: str = "USD") -> float:
    """Ambil kurs base→IDR. base: 'USD' atau 'MYR'."""
    global _kurs_cache
    if base in _kurs_cache:
        return _kurs_cache[base]
    try:
        r = requests.get(
            f"https://open.er-api.com/v6/latest/{base.upper()}",
            timeout=8
        ).json()
        rate = float(r["rates"]["IDR"])
        _kurs_cache[base] = rate
        return rate
    except Exception:
        defaults = {"USD": 16500.0, "MYR": 3800.0, "GBP": 21000.0}
        return defaults.get(base.upper(), 16500.0)


# ============================================================
# HARGA CPO GLOBAL — CPO=F (NYMEX, USD/MT)
# ============================================================

def _yf_history_safe(ticker: str, period: str) -> pd.DataFrame:
    """Ambil riwayat harga via yf.Ticker().history(). Return DataFrame kosong jika gagal."""
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        # Normalkan nama kolom
        rename = {}
        for c in df.columns:
            cu = str(c).upper()
            if "DATE" in cu:      rename[c] = "Date"
            elif "CLOSE" in cu:   rename[c] = "Close"
            elif "HIGH" in cu:    rename[c] = "High"
            elif "LOW" in cu:     rename[c] = "Low"
            elif "VOLUME" in cu:  rename[c] = "Volume"
        df = df.rename(columns=rename)
        if "Date" not in df.columns or "Close" not in df.columns:
            return pd.DataFrame()
        df["Date"]  = pd.to_datetime(df["Date"]).dt.date
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna(subset=["Close"]).sort_values("Date").reset_index(drop=True)
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


_CPO_GLOBAL_TICKERS = [
    ("CPO=F",  "USD", "NYMEX CPO Futures"),
    ("PALM.L", "GBP", "WisdomTree Palm Oil ETC (London)"),
]


def get_cpo_global(period: str = "1y") -> pd.DataFrame:
    """
    Ambil harga CPO global. Prioritas: CPO=F (USD) → PALM.L (GBP).
    Kolom hasil: Date, Close, MA20, MA50, Pct_Change, Close_IDR, Currency, Source
    """
    df       = pd.DataFrame()
    currency = "USD"
    source   = ""

    if YFINANCE_OK:
        for ticker, cur, label in _CPO_GLOBAL_TICKERS:
            df = _yf_history_safe(ticker, period)
            if not df.empty:
                currency = cur
                source   = f"{label} ({ticker})"
                break

    if df.empty:
        return pd.DataFrame()

    # Indikator teknikal
    n = len(df)
    win20 = min(20, max(2, n // 3))
    win50 = min(50, max(2, n // 2))
    df["MA20"]       = df["Close"].rolling(win20).mean()
    df["MA50"]       = df["Close"].rolling(win50).mean()
    df["Pct_Change"] = df["Close"].pct_change() * 100

    kurs             = get_kurs_idr(currency)
    df["Close_IDR"]  = df["Close"] * kurs
    df["Currency"]   = currency
    df["Source"]     = source
    return df


# ============================================================
# HARGA CPO LOKAL INDONESIA
# ============================================================

def get_cpo_indonesia_kpbn() -> pd.DataFrame:
    """
    Scraping harga CPO dari KPBN (PTPN Trading).
    Return DataFrame: Date, Close_IDR, Source
    """
    try:
        url = "https://www.kpbn.co.id/harga.php"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")

        from bs4 import BeautifulSoup
        soup  = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            raise Exception("Tabel tidak ditemukan")

        rows = []
        for tr in table.find_all("tr")[1:]:
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) >= 2:
                try:
                    price_str = re.sub(r"[^\d,.]", "", cols[1]).replace(",", "")
                    price     = float(price_str)
                    date      = pd.to_datetime(cols[0], dayfirst=True).date()
                    rows.append({"Date": date, "Close_IDR": price})
                except Exception:
                    continue

        if not rows:
            raise Exception("Tidak ada baris valid")

        df = (pd.DataFrame(rows)
              .sort_values("Date")
              .reset_index(drop=True))
        df["Source"] = "KPBN"
        return df
    except Exception:
        return pd.DataFrame()


def get_cpo_indonesia(period: str = "1y") -> pd.DataFrame:
    """
    Harga CPO lokal Indonesia (IDR/ton).
    Prioritas: KPBN → estimasi dari CPO=F * kurs USD/IDR
    """
    df = get_cpo_indonesia_kpbn()
    if not df.empty:
        n = len(df)
        df["MA20"]       = df["Close_IDR"].rolling(min(5, n)).mean()
        df["MA50"]       = df["Close_IDR"].rolling(min(20, n)).mean()
        df["Pct_Change"] = df["Close_IDR"].pct_change() * 100
        return df

    # Fallback: CPO=F dikonversi ke IDR
    df_global = get_cpo_global(period)
    if df_global.empty:
        return pd.DataFrame()

    kurs = get_kurs_idr("USD")
    df_idr              = df_global[["Date", "Close", "Pct_Change"]].copy()
    df_idr["Close_IDR"] = df_global["Close"] * kurs
    n = len(df_idr)
    df_idr["MA20"]      = df_idr["Close_IDR"].rolling(min(20, n)).mean()
    df_idr["MA50"]      = df_idr["Close_IDR"].rolling(min(50, n)).mean()
    df_idr["Source"]    = "Estimasi (CPO=F × kurs USD/IDR)"
    return df_idr


# ============================================================
# STATISTIK RINGKASAN
# ============================================================

def cpo_summary(df: pd.DataFrame, price_col: str = "Close") -> dict:
    """Hitung harga terkini, perubahan, dan high/low 52 minggu."""
    if df.empty or price_col not in df.columns:
        return {}
    s = df[price_col].dropna()
    if s.empty:
        return {}
    current  = float(s.iloc[-1])
    prev     = float(s.iloc[-2]) if len(s) > 1 else current
    chg      = current - prev
    chg_pct  = (chg / prev * 100) if prev else 0
    high_52w = float(s.tail(252).max())
    low_52w  = float(s.tail(252).min())
    return {
        "current":  current,
        "change":   chg,
        "chg_pct":  chg_pct,
        "high_52w": high_52w,
        "low_52w":  low_52w,
    }


# ============================================================
# HARGA MINYAK GORENG JAWA TIMUR — SISKAPERBAPO
# ============================================================

_SISKAPERBA_BASE = "https://siskaperbapo.jatimprov.go.id"

# Commodity IDs dari SISKAPERBAPO Jawa Timur
_MINYAK_GORENG_IDS = {
    "Minyak Goreng Curah":             10,
    "Minyak Goreng Kemasan Premium":   92,
    "Minyak Goreng Kemasan Sederhana": 95,
    "Minyak Goreng MINYAKITA":         96,
}


def _siskap_tooltip(commodity_id: int, date) -> float | None:
    """
    Ambil harga dari API SISKAPERBAPO untuk 1 komoditas 1 tanggal.
    Return float harga atau None jika gagal.
    """
    try:
        url = (f"{_SISKAPERBA_BASE}/home2/getTooltipData"
               f"?commodity_id={commodity_id}&date={date}")
        r = _http_get(url, timeout=6)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("success"):
            return None
        res = data.get("result", {})
        ha = res.get("harga_akhir")
        return float(ha) if ha else None
    except Exception:
        return None


def get_minyakgoreng_current() -> dict:
    """
    Ambil harga terkini semua jenis minyak goreng dari SISKAPERBAPO Jatim.
    Return dict: {nama: {"harga": float, "satuan": str, "harga_awal": float, ...}}
    """
    today = datetime.now().date()
    result = {}
    try:
        for nama, cid in _MINYAK_GORENG_IDS.items():
            url = (f"{_SISKAPERBA_BASE}/home2/getTooltipData"
                   f"?commodity_id={cid}&date={today}")
            r = _http_get(url, timeout=6)
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and data.get("result"):
                    res = data["result"]
                    result[nama] = {
                        "harga":       float(res.get("harga_akhir") or 0),
                        "harga_awal":  float(res.get("harga_awal") or 0),
                        "satuan":      res.get("bp_satuan", ""),
                        "tgl_awal":    res.get("tanggal_awal", ""),
                        "tgl_akhir":   res.get("tanggal_akhir", ""),
                        "commodity_id": cid,
                    }
    except Exception:
        pass
    return result


def get_minyakgoreng_history(commodity_id: int = 10, days: int = 30) -> pd.DataFrame:
    """
    Ambil riwayat harga minyak goreng dari SISKAPERBAPO Jatim.
    Melakukan days+1 API call (1 per hari). Default: Minyak Goreng Curah (ID=10).
    """
    today = datetime.now().date()
    rows  = []
    for d in range(days, -1, -1):
        date = today - timedelta(days=d)
        price = _siskap_tooltip(commodity_id, date)
        if price and price > 0:
            rows.append({"Date": date, "Harga": price})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)
    n = len(df)
    df["MA7"]  = df["Harga"].rolling(min(7, n)).mean()
    df["MA14"] = df["Harga"].rolling(min(14, n)).mean()
    return df


def get_minyakgoreng_all_history(days: int = 14) -> pd.DataFrame:
    """
    Ambil riwayat harga semua jenis minyak goreng dari SISKAPERBAPO.
    Return long-format DataFrame: Date, Jenis, Harga
    """
    today = datetime.now().date()
    rows  = []
    for d in range(days, -1, -1):
        date = today - timedelta(days=d)
        for nama, cid in _MINYAK_GORENG_IDS.items():
            price = _siskap_tooltip(cid, date)
            if price and price > 0:
                rows.append({"Date": date, "Jenis": nama, "Harga": price})

    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
            .sort_values(["Date", "Jenis"])
            .reset_index(drop=True))


# ============================================================
# BERITA & SENTIMEN CPO
# ============================================================

_POS = {"naik","laba","untung","positif","menguat","tumbuh","bullish",
        "rally","surplus","profit","meningkat","rebound","optimis",
        "gain","up","rise","strong","boost","higher","recover"}
_NEG = {"turun","rugi","anjlok","negatif","melemah","buruk","bearish",
        "koreksi","defisit","loss","menurun","terpuruk","pesimis",
        "down","fall","drop","weak","decline","lower","crash"}


def _clean(text: str) -> str:
    if pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    if SASTRAWI_OK and _sw:
        text = _sw.remove(text)
    return text


def _score(text: str) -> int:
    s = 0
    for w in text.split():
        if w in _POS: s += 1
        if w in _NEG: s -= 1
    return s


def get_cpo_news(days: int = 14, lang: str = "id") -> pd.DataFrame:
    """
    Ambil berita CPO dari Google News RSS.
    lang='id' → Indonesia, lang='en' → Global
    """
    if not FEEDPARSER_OK:
        return pd.DataFrame()

    if lang == "id":
        keywords         = ["harga CPO", "minyak sawit Indonesia", "kelapa sawit harga"]
        hl, gl, ceid     = "id", "ID", "ID:id"
    else:
        keywords         = ["CPO price", "crude palm oil", "palm oil futures"]
        hl, gl, ceid     = "en", "US", "US:en"

    data  = []
    end   = datetime.now()
    start = end - timedelta(days=days)

    for kw in keywords:
        kw_enc = urllib.parse.quote(kw)
        url    = (
            f"https://news.google.com/rss/search"
            f"?q={kw_enc}+after:{start.date()}+before:{end.date()}"
            f"&hl={hl}&gl={gl}&ceid={ceid}"
        )
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                try:
                    pub = pd.to_datetime(e.published).date()
                except Exception:
                    pub = datetime.now().date()
                data.append({
                    "Date":    pub,
                    "title":   e.get("title", ""),
                    "desc":    e.get("summary", ""),
                    "media":   e.source.title if hasattr(e, "source") else "",
                    "keyword": kw,
                })
        except Exception:
            continue

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data).drop_duplicates(subset="title")
    df["doc"]             = (df["title"] + " " + df["desc"]).apply(_clean)
    df["sentiment_score"] = df["doc"].apply(_score)
    df["sentiment_label"] = df["sentiment_score"].apply(
        lambda s: "Positif" if s > 0 else ("Negatif" if s < 0 else "Netral")
    )
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


def get_minyakgoreng_news(days: int = 14) -> pd.DataFrame:
    """
    Ambil berita minyak goreng Indonesia dari Google News RSS.
    """
    if not FEEDPARSER_OK:
        return pd.DataFrame()

    keywords     = ["harga minyak goreng", "minyak goreng Indonesia", "minyak goreng naik turun"]
    hl, gl, ceid = "id", "ID", "ID:id"

    data  = []
    end   = datetime.now()
    start = end - timedelta(days=days)

    for kw in keywords:
        kw_enc = urllib.parse.quote(kw)
        url    = (
            f"https://news.google.com/rss/search"
            f"?q={kw_enc}+after:{start.date()}+before:{end.date()}"
            f"&hl={hl}&gl={gl}&ceid={ceid}"
        )
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                try:
                    pub = pd.to_datetime(e.published).date()
                except Exception:
                    pub = datetime.now().date()
                data.append({
                    "Date":    pub,
                    "title":   e.get("title", ""),
                    "desc":    e.get("summary", ""),
                    "media":   e.source.title if hasattr(e, "source") else "",
                    "keyword": kw,
                })
        except Exception:
            continue

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data).drop_duplicates(subset="title")
    df["doc"]             = (df["title"] + " " + df["desc"]).apply(_clean)
    df["sentiment_score"] = df["doc"].apply(_score)
    df["sentiment_label"] = df["sentiment_score"].apply(
        lambda s: "Positif" if s > 0 else ("Negatif" if s < 0 else "Netral")
    )
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


def get_cpo_wordcloud(df: pd.DataFrame):
    """Buat WordCloud dari kolom doc. Return (wc_image, top_words_list)."""
    if df.empty or "doc" not in df.columns:
        return None, None
    text   = " ".join(df["doc"].dropna())
    common = Counter(text.split()).most_common(10) if text.strip() else None
    wc     = None
    if text.strip() and WORDCLOUD_OK:
        try:
            wc = WordCloud(background_color="white", width=600, height=300).generate(text)
        except Exception:
            wc = None
    return wc, common
