"""
Sentiment Analysis + LSTM Prediction Module
Analisis sentimen berita Google News dan prediksi harga dengan LSTM.
"""

import os
import re
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone

import feedparser
import numpy as np
import pandas as pd
import requests

# ============================================================
# OPTIONAL IMPORTS (tidak wajib — dihandle gracefully)
# ============================================================

try:
    from wordcloud import WordCloud
    WORDCLOUD_OK = True
except ImportError:
    WORDCLOUD_OK = False

try:
    from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
    factory = StopWordRemoverFactory()
    _stopword = factory.create_stop_word_remover()
    SASTRAWI_OK = True
except ImportError:
    SASTRAWI_OK = False
    _stopword = None

try:
    from alpha_vantage.timeseries import TimeSeries
    ALPHA_OK = True
except ImportError:
    ALPHA_OK = False

try:
    from sklearn.preprocessing import MinMaxScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense
    TENSORFLOW_OK = True
except ImportError:
    TENSORFLOW_OK = False

# ============================================================
# CONFIG
# ============================================================

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "YQNUKAH419JA2RYV")
HEADERS = {"User-Agent": "Mozilla/5.0"}

POS_WORDS = {"naik","laba","untung","positif","menguat","tumbuh","bullish","rally","surplus","profit"}
NEG_WORDS = {"turun","rugi","anjlok","negatif","melemah","buruk","bearish","koreksi","defisit","loss"}

# ============================================================
# SMART KEYWORD
# ============================================================

def smart_keyword(keyword: str, ticker: str):
    if not keyword or keyword.strip() == "":
        keyword = ticker
    keyword = " ".join(str(keyword).replace("\n", " ").replace("\r", " ").split())
    suggestions = [
        keyword,
        f"saham {keyword}",
        f"{keyword} Indonesia",
        f"{keyword} berita",
        f"{keyword} stock",
    ]
    return keyword, suggestions, urllib.parse.quote(keyword)

# ============================================================
# KURS USD → IDR
# ============================================================

def get_kurs() -> float:
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=IDR",
            timeout=5
        ).json()
        return r["rates"]["IDR"]
    except Exception:
        return 15500

# ============================================================
# TEXT PREPROCESSING
# ============================================================

def preprocess_text(text: str) -> str:
    if pd.isna(text):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    if SASTRAWI_OK and _stopword:
        text = _stopword.remove(text)
    return text

# ============================================================
# SENTIMENT SCORING
# ============================================================

def sentiment_score(text: str) -> int:
    score = 0
    for w in text.split():
        if w in POS_WORDS:
            score += 1
        if w in NEG_WORDS:
            score -= 1
    return score

def sentiment_label(score: int) -> str:
    if score > 0:
        return "Positif"
    elif score < 0:
        return "Negatif"
    return "Netral"

# ============================================================
# DATA HARGA — YAHOO FINANCE
# ============================================================

def get_yahoo(symbol: str, start, end, is_indo: bool):

    def to_unix(d):
        return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())

    sym = f"{symbol}.JK" if is_indo else symbol
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"

    try:
        r = requests.get(url, headers=HEADERS, params={
            "interval": "1d",
            "period1": to_unix(start),
            "period2": to_unix(end + timedelta(days=1)),
        }, timeout=10)
        data = r.json()
    except Exception:
        return None

    result = data.get("chart", {}).get("result")
    if not result:
        return None

    ts    = result[0]["timestamp"]
    close = result[0]["indicators"]["quote"][0]["close"]

    df = pd.DataFrame({
        "Date":  [datetime.fromtimestamp(t).date() for t in ts],
        "Close": close,
    }).dropna()

    df["Prev_Close"]    = df["Close"].shift(1)
    df["Price_Change"]  = df["Close"] - df["Prev_Close"]
    df["Pct_Change (%)"] = (df["Price_Change"] / df["Prev_Close"]) * 100

    if not is_indo:
        df["Close_IDR"] = df["Close"] * get_kurs()

    return df


def get_full_history(symbol: str, is_indo: bool):
    return get_yahoo(
        symbol,
        datetime.now() - timedelta(days=365 * 3),
        datetime.now(),
        is_indo,
    )

# ============================================================
# DATA HARGA — ALPHA VANTAGE
# ============================================================

def get_alpha(symbol: str, start, end):
    if not ALPHA_OK:
        return None
    try:
        ts_api = TimeSeries(key=ALPHA_VANTAGE_KEY, output_format="pandas")
        data, _ = ts_api.get_daily(symbol=symbol)
        df = data.rename(columns={"4. close": "Close"})
        df.index = pd.to_datetime(df.index)
        df = df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))]
        df = df.reset_index().rename(columns={"index": "Date"})
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        df["Prev_Close"]    = df["Close"].shift(1)
        df["Price_Change"]  = df["Close"] - df["Prev_Close"]
        df["Pct_Change (%)"] = (df["Price_Change"] / df["Prev_Close"]) * 100
        df["Close_IDR"] = df["Close"] * get_kurs()
        return df
    except Exception:
        return None

# ============================================================
# NEWS + SENTIMENT
# ============================================================

def get_news(keyword_encoded: str, start, end):
    data = []
    for d in pd.date_range(start, end):
        url = (
            f"https://news.google.com/rss/search?q={keyword_encoded}"
            f"+after:{d.date()}+before:{(d + timedelta(days=1)).date()}"
            f"&hl=id&gl=ID&ceid=ID:id"
        )
        feed = feedparser.parse(url)
        for e in feed.entries:
            data.append({
                "Date":  pd.to_datetime(e.published).date(),
                "title": e.title,
                "desc":  getattr(e, "summary", ""),
                "media": e.source.title if hasattr(e, "source") else "",
            })

    if not data:
        return None, None, None, None, None

    df = pd.DataFrame(data).drop_duplicates(subset="title")
    df["doc"] = (df["title"] + " " + df["desc"]).apply(preprocess_text)
    df["sentiment_score"] = df["doc"].apply(sentiment_score)
    df["sentiment_label"] = df["sentiment_score"].apply(sentiment_label)

    text = " ".join(df["doc"])

    wc, common = None, None
    if text.strip() and WORDCLOUD_OK:
        wc = WordCloud(background_color="white").generate(text)
    if text.strip():
        common = Counter(text.split()).most_common(10)

    media    = df["media"].value_counts().head(10)
    df_daily = df.groupby("Date")["title"].apply(lambda x: " | ".join(x)).reset_index()
    sent     = df.groupby("Date")["sentiment_score"].mean().reset_index()
    df_daily = pd.merge(df_daily, sent, on="Date", how="left")

    return df, df_daily, wc, common, media

# ============================================================
# PREDIKSI HARGA — sklearn MLP (pengganti LSTM, tanpa TensorFlow)
# ============================================================

def predict_lstm(df: pd.DataFrame):
    """Prediksi harga dengan sliding-window + MLPRegressor (sklearn).
    Nama fungsi dipertahankan agar kompatibel dengan pemanggil lama."""
    if not SKLEARN_OK:
        return None, "scikit-learn belum terinstall: pip install scikit-learn"

    data = df[["Close"]].values
    if len(data) < 20:
        return None, "Data historis terlalu sedikit (minimal 20 hari)."

    from sklearn.neural_network import MLPRegressor

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(data).flatten()

    lookback = 10
    X, y = [], []
    for i in range(lookback, len(scaled)):
        X.append(scaled[i - lookback:i])
        y.append(scaled[i])

    X, y = np.array(X), np.array(y)

    model = MLPRegressor(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        max_iter=300,
        random_state=42,
    )
    model.fit(X, y)

    pred = model.predict(X)
    pred = scaler.inverse_transform(pred.reshape(-1, 1)).flatten()

    df_out = df.iloc[lookback:].copy()
    df_out["Prediksi"] = pred

    return df_out, None

# ============================================================
# REKOMENDASI TRADING
# ============================================================

def generate_recommendation(df_range: pd.DataFrame):
    if df_range is None or len(df_range) < 3:
        return "Data tidak cukup", "Data tidak cukup"

    df = df_range.dropna(subset=["sentiment_score", "Pct_Change (%)"])
    if len(df) < 3:
        return "Data tidak cukup", "Data tidak cukup"

    last       = df.tail(3)
    avg_sent   = last["sentiment_score"].mean()
    avg_return = last["Pct_Change (%)"].mean()
    trend      = last["Pct_Change (%)"].diff().mean()

    if avg_sent > 0.5 and avg_return > 0:
        today = "BELI"
    elif avg_sent < 0 and avg_return < 0:
        today = "JANGAN BELI"
    else:
        today = "PANTAU"

    if avg_sent > 0.5 and trend > 0:
        tomorrow = "BELI"
    elif avg_sent < 0 and trend < 0:
        tomorrow = "JANGAN BELI"
    else:
        tomorrow = "PANTAU"

    return today, tomorrow
