"""
Forecast & Analytics Engine — CPO Monitor
Menyediakan:
  - Price forecasting (GradientBoosting + lag features, no data leakage)
  - Lag correlation analysis
  - Sentiment lead-lag analysis
  - Rolling volatility + anomaly detection
"""

import numpy as np
import pandas as pd
from datetime import timedelta


# ============================================================
# HELPER: LAG FEATURE BUILDER
# ============================================================

def _build_lag_df(series: pd.Series, n_lags: int) -> pd.DataFrame:
    df = {f"lag_{i}": series.shift(i).values for i in range(1, n_lags + 1)}
    df["target"] = series.values
    return pd.DataFrame(df).dropna()


# ============================================================
# VISUALISASI 1 — PRICE FORECASTING
# ============================================================

def forecast_gb(
    dates:   pd.Series,
    values:  pd.Series,
    horizon: int = 30,
    n_lags:  int = 14,
):
    """
    Forecast menggunakan GradientBoostingRegressor + lag features.
    Train/val split mencegah data leakage.
    CI melebar seiring horizon (ketidakpastian makin besar).

    Returns
    -------
    df_forecast : DataFrame kolom Date, Forecast, Upper, Lower
    ci_base     : float — lebar CI pada hari pertama
    """
    from sklearn.ensemble import GradientBoostingRegressor

    series = pd.Series(values.values, index=pd.to_datetime(dates)).dropna().sort_index()
    if len(series) < n_lags + 15:
        return pd.DataFrame(), 0.0

    feat_df = _build_lag_df(series, n_lags)
    X = feat_df.drop(columns="target").values
    y = feat_df["target"].values

    # 80/20 split — val dipakai untuk estimasi CI, bukan untuk training
    split = max(int(len(X) * 0.8), len(X) - 60)
    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=3,
        learning_rate=0.05, subsample=0.8,
        random_state=42
    )
    model.fit(X[:split], y[:split])
    ci_base = float(np.std(y[split:] - model.predict(X[split:])) * 1.96)

    # Iterative multi-step forecast
    window = list(series.values[-n_lags:])
    preds  = []
    for _ in range(horizon):
        x = np.array(window[-n_lags:][::-1]).reshape(1, -1)
        p = float(model.predict(x)[0])
        preds.append(p)
        window.append(p)

    fd = pd.date_range(start=series.index[-1] + timedelta(days=1),
                       periods=horizon, freq="D")

    # CI melebar secara linear dengan horizon
    ci_width = [ci_base * (1 + i * 0.04) for i in range(horizon)]

    return pd.DataFrame({
        "Date":     fd,
        "Forecast": preds,
        "Upper":    [p + ci for p, ci in zip(preds, ci_width)],
        "Lower":    [max(0, p - ci) for p, ci in zip(preds, ci_width)],
    }), ci_base


# ============================================================
# VISUALISASI 2 — CORRELATION & LAG ANALYSIS
# ============================================================

def lag_correlation(
    s1: pd.Series,
    s2: pd.Series,
    max_lag: int = 14,
) -> dict:
    """
    Hitung Pearson correlation antara s1 dan s2.shift(lag) untuk lag 0..max_lag.
    s1 = seri leading (CPO global), s2 = seri lagging (minyak goreng).
    Interpretasi: lag positif = s2 bereaksi SETELAH s1 bergerak.
    """
    s1 = s1.dropna().sort_index()
    s2 = s2.dropna().sort_index()
    result = {}
    for lag in range(0, max_lag + 1):
        s2_sh  = s2.shift(lag) if lag > 0 else s2
        common = s1.index.intersection(s2_sh.dropna().index)
        if len(common) < 8:
            result[lag] = 0.0
            continue
        corr = s1[common].corr(s2_sh[common])
        result[lag] = round(float(corr), 4) if not np.isnan(corr) else 0.0
    return result


def build_correlation_matrix(
    df_cpo: pd.DataFrame,
    df_mg: pd.DataFrame,
    mg_label: str = "Minyak Goreng (IDR/kg)",
) -> pd.DataFrame:
    """
    Buat DataFrame korelasi Pearson antara CPO IDR dan Minyak Goreng.
    """
    cpo = (df_cpo.assign(Date=pd.to_datetime(df_cpo["Date"]))
           .set_index("Date")["Close_IDR"]
           .sort_index()
           .rename("CPO Global (IDR/ton)"))

    mg  = (df_mg.assign(Date=pd.to_datetime(df_mg["Date"]))
           .set_index("Date")["Harga"]
           .sort_index()
           .rename(mg_label))

    combined = pd.concat([cpo, mg], axis=1).dropna()
    if combined.empty:
        return pd.DataFrame()
    return combined.corr()


# ============================================================
# VISUALISASI 3 — SENTIMENT IMPACT ANALYTICS
# ============================================================

def sentiment_lead_lag(
    df_price: pd.DataFrame,
    df_news:  pd.DataFrame,
    price_col: str = "Close_IDR",
    max_lag: int = 7,
) -> dict:
    """
    Hitung korelasi antara skor sentimen hari ini dan perubahan harga
    beberapa hari ke depan (lag 1..max_lag).
    Nilai positif → sentimen bullish mendahului kenaikan harga.
    """
    if df_news is None or df_news.empty:
        return {}
    if df_price is None or df_price.empty or price_col not in df_price.columns:
        return {}

    price = (df_price.assign(Date=pd.to_datetime(df_price["Date"]))
             .set_index("Date")[price_col]
             .sort_index())
    pct = price.pct_change() * 100

    sent = (df_news.assign(Date=pd.to_datetime(df_news["Date"]))
            .groupby("Date")["sentiment_score"]
            .mean()
            .sort_index())

    result = {}
    for lag in range(1, max_lag + 1):
        future = pct.shift(-lag)
        common = sent.index.intersection(future.dropna().index)
        if len(common) < 5:
            result[lag] = 0.0
            continue
        corr = sent[common].corr(future[common])
        result[lag] = round(float(corr), 4) if not np.isnan(corr) else 0.0
    return result


def build_sentiment_price_df(
    df_price: pd.DataFrame,
    df_news:  pd.DataFrame,
    price_col: str = "Close_IDR",
) -> pd.DataFrame:
    """
    Gabungkan harga harian dan rata-rata sentimen harian pada timeline yang sama.
    """
    if df_news is None or df_news.empty:
        return pd.DataFrame()
    if df_price is None or df_price.empty or price_col not in df_price.columns:
        return pd.DataFrame()

    price = (df_price.assign(Date=pd.to_datetime(df_price["Date"]))
             .set_index("Date")[[price_col]]
             .sort_index())

    sent  = (df_news.assign(Date=pd.to_datetime(df_news["Date"]))
             .groupby("Date")["sentiment_score"]
             .mean()
             .rename("sentiment")
             .to_frame())

    combined = price.join(sent, how="inner").dropna()
    combined.index.name = "Date"
    return combined.reset_index()


# ============================================================
# VISUALISASI 4 — VOLATILITY & ANOMALY DETECTION
# ============================================================

def rolling_volatility(series: pd.Series, window: int = 30):
    """
    Hitung rolling std (volatilitas) dan deteksi anomali harga harian.
    Anomali = |z-score| > 2 (lebih dari 2 standar deviasi dari MA).

    Returns
    -------
    vol    : pd.Series — rolling std
    ma     : pd.Series — rolling mean
    anomalies : pd.Series — titik data yang merupakan anomali
    """
    vol  = series.rolling(window, min_periods=5).std()
    ma   = series.rolling(window, min_periods=5).mean()
    z    = (series - ma) / vol.replace(0, np.nan)
    anom = series[z.abs() > 2]
    return vol, ma, anom
