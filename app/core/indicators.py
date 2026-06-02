import pandas as pd
import numpy as np


# ======================================================
# EMA — Exponential Moving Average
# ======================================================

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


# ======================================================
# SMA — Simple Moving Average
# ======================================================

def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


# ======================================================
# RSI — Relative Strength Index (TradingView / Wilder)
# ======================================================

def rsi(series: pd.Series, period=14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ======================================================
# MACD — Moving Average Convergence Divergence
# ======================================================

def macd(
    series: pd.Series,
    fast=12,
    slow=26,
    signal=9
):
    """Returns: (macd_line, signal_line, histogram)"""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ======================================================
# BOLLINGER BANDS
# ======================================================

def bollinger_bands(
    series: pd.Series,
    period=20,
    std_dev=2.0
):
    """
    Returns: (upper, middle, lower)
    - Squeeze: upper-lower menyempit → breakout akan datang
    - %B = (price - lower) / (upper - lower)
    """
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def bollinger_pct_b(series: pd.Series, period=20, std_dev=2.0) -> pd.Series:
    """%B: 0 = di lower band, 1 = di upper band, >1 = overbought, <0 = oversold"""
    upper, middle, lower = bollinger_bands(series, period, std_dev)
    return (series - lower) / (upper - lower + 1e-10)


def bollinger_bandwidth(series: pd.Series, period=20, std_dev=2.0) -> pd.Series:
    """Bandwidth: nilai rendah = squeeze, nilai tinggi = volatilitas tinggi"""
    upper, middle, lower = bollinger_bands(series, period, std_dev)
    return (upper - lower) / (middle + 1e-10)


# ======================================================
# ATR — Average True Range
# ======================================================

def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period=14
) -> pd.Series:
    """
    Volatilitas pasar. Digunakan untuk:
    - Menentukan stop loss dinamis
    - Filter saham yang bergerak cukup lebar
    """
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ======================================================
# STOCHASTIC RSI
# ======================================================

def stochastic_rsi(
    series: pd.Series,
    rsi_period=14,
    stoch_period=14,
    smooth_k=3,
    smooth_d=3
):
    """
    Lebih sensitif dari RSI biasa.
    Returns: (%K, %D)
    - <20: oversold, >80: overbought
    - %K cross %D dari bawah = sinyal beli
    """
    rsi_vals = rsi(series, rsi_period)
    rsi_min = rsi_vals.rolling(stoch_period).min()
    rsi_max = rsi_vals.rolling(stoch_period).max()
    raw_k = (rsi_vals - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100
    k = raw_k.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


# ======================================================
# STOCHASTIC OSCILLATOR (%K, %D)
# ======================================================

def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period=14,
    smooth_k=3,
    smooth_d=3
):
    """
    Returns: (%K, %D)
    - <20: oversold, >80: overbought
    """
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    raw_k = (close - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
    k = raw_k.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


# ======================================================
# ADX — Average Directional Index
# ======================================================

def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period=14
):
    """
    Kekuatan tren (bukan arah).
    Returns: (adx_val, plus_di, minus_di)
    - ADX > 25: tren kuat
    - +DI > -DI: tren naik
    - -DI > +DI: tren turun
    """
    atr_val = atr(high, low, close, period)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where(
        (up_move > down_move) & (up_move > 0), up_move, 0.0
    )
    minus_dm = np.where(
        (down_move > up_move) & (down_move > 0), down_move, 0.0
    )

    plus_dm_s = pd.Series(plus_dm, index=high.index)
    minus_dm_s = pd.Series(minus_dm, index=high.index)

    smooth_tr = atr_val
    smooth_plus = plus_dm_s.ewm(alpha=1 / period, adjust=False).mean()
    smooth_minus = minus_dm_s.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * smooth_plus / (smooth_tr + 1e-10)
    minus_di = 100 * smooth_minus / (smooth_tr + 1e-10)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()

    return adx_val, plus_di, minus_di


# ======================================================
# SUPERTREND
# ======================================================

def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period=10,
    multiplier=3.0
):
    """
    Trend-following dengan stop loss dinamis.
    Returns: (supertrend_line, direction)
    - direction = 1 → tren naik (BUY)
    - direction = -1 → tren turun (SELL)
    """
    atr_val = atr(high, low, close, period)
    hl2 = (high + low) / 2

    basic_upper = hl2 + multiplier * atr_val
    basic_lower = hl2 - multiplier * atr_val

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    st_line = pd.Series(np.nan, index=close.index)
    direction = pd.Series(0, index=close.index)

    for i in range(1, len(close)):
        # Final upper band
        if (basic_upper.iloc[i] < final_upper.iloc[i - 1]
                or close.iloc[i - 1] > final_upper.iloc[i - 1]):
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        # Final lower band
        if (basic_lower.iloc[i] > final_lower.iloc[i - 1]
                or close.iloc[i - 1] < final_lower.iloc[i - 1]):
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        # Direction
        if np.isnan(st_line.iloc[i - 1]):
            direction.iloc[i] = 1
            st_line.iloc[i] = final_lower.iloc[i]
        elif st_line.iloc[i - 1] == final_upper.iloc[i - 1]:
            if close.iloc[i] <= final_upper.iloc[i]:
                direction.iloc[i] = -1
                st_line.iloc[i] = final_upper.iloc[i]
            else:
                direction.iloc[i] = 1
                st_line.iloc[i] = final_lower.iloc[i]
        else:
            if close.iloc[i] >= final_lower.iloc[i]:
                direction.iloc[i] = 1
                st_line.iloc[i] = final_lower.iloc[i]
            else:
                direction.iloc[i] = -1
                st_line.iloc[i] = final_upper.iloc[i]

    return st_line, direction


# ======================================================
# OBV — On Balance Volume
# ======================================================

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Akumulasi/distribusi berbasis volume.
    - OBV naik saat harga flat → akumulasi diam-diam
    - OBV turun saat harga flat → distribusi
    """
    signed_vol = np.where(
        close.diff() > 0, volume,
        np.where(close.diff() < 0, -volume, 0)
    )
    return pd.Series(signed_vol, index=close.index).cumsum()


# ======================================================
# VWAP — Volume Weighted Average Price
# ======================================================

def vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series
) -> pd.Series:
    """
    Harga rata-rata tertimbang volume (terbaik untuk intraday).
    - Harga > VWAP: bullish bias
    - Harga < VWAP: bearish bias
    """
    typical_price = (high + low + close) / 3
    return (typical_price * volume).cumsum() / volume.cumsum()


# ======================================================
# WILLIAMS %R
# ======================================================

def williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period=14
) -> pd.Series:
    """
    -0 to -20: overbought
    -80 to -100: oversold
    """
    highest_high = high.rolling(period).max()
    lowest_low = low.rolling(period).min()
    return -100 * (highest_high - close) / (highest_high - lowest_low + 1e-10)


# ======================================================
# CCI — Commodity Channel Index
# ======================================================

def cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period=20
) -> pd.Series:
    """
    >100: overbought / momentum kuat ke atas
    <-100: oversold / momentum kuat ke bawah
    """
    typical_price = (high + low + close) / 3
    sma_tp = typical_price.rolling(period).mean()
    mean_dev = typical_price.rolling(period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    return (typical_price - sma_tp) / (0.015 * mean_dev + 1e-10)


# ======================================================
# MFI — Money Flow Index
# ======================================================

def mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period=14
) -> pd.Series:
    """
    RSI berbasis volume (smart money).
    >80: overbought, <20: oversold
    """
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume

    positive_flow = pd.Series(
        np.where(typical_price > typical_price.shift(1), money_flow, 0),
        index=close.index
    )
    negative_flow = pd.Series(
        np.where(typical_price < typical_price.shift(1), money_flow, 0),
        index=close.index
    )

    pos_mf = positive_flow.rolling(period).sum()
    neg_mf = negative_flow.rolling(period).sum()

    mfr = pos_mf / (neg_mf + 1e-10)
    return 100 - (100 / (1 + mfr))


# ======================================================
# FIBONACCI RETRACEMENT LEVELS
# ======================================================

def fibonacci_levels(high_val: float, low_val: float) -> dict:
    """
    Level Fibonacci dari swing high ke swing low.
    Digunakan untuk menemukan support/resistance.
    """
    diff = high_val - low_val
    return {
        "0.0":   round(high_val, 2),
        "23.6":  round(high_val - 0.236 * diff, 2),
        "38.2":  round(high_val - 0.382 * diff, 2),
        "50.0":  round(high_val - 0.500 * diff, 2),
        "61.8":  round(high_val - 0.618 * diff, 2),
        "78.6":  round(high_val - 0.786 * diff, 2),
        "100.0": round(low_val, 2),
    }


# ======================================================
# ICHIMOKU CLOUD
# ======================================================

def ichimoku(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    tenkan_period=9,
    kijun_period=26,
    senkou_b_period=52,
    displacement=26
):
    """
    Ichimoku Kinko Hyo.
    Returns: (tenkan, kijun, senkou_a, senkou_b, chikou)
    - Harga di atas cloud: bullish
    - Harga di bawah cloud: bearish
    - Tenkan cross Kijun ke atas: sinyal beli
    """
    def donchian_mid(period):
        return (high.rolling(period).max() + low.rolling(period).min()) / 2

    tenkan = donchian_mid(tenkan_period)
    kijun = donchian_mid(kijun_period)
    senkou_a = ((tenkan + kijun) / 2).shift(displacement)
    senkou_b = donchian_mid(senkou_b_period).shift(displacement)
    chikou = close.shift(-displacement)

    return tenkan, kijun, senkou_a, senkou_b, chikou


# ======================================================
# PIVOT POINTS (Classic)
# ======================================================

def pivot_points(high_val: float, low_val: float, close_val: float) -> dict:
    """
    Classic pivot points untuk level support/resistance harian.
    """
    pp = (high_val + low_val + close_val) / 3
    r1 = 2 * pp - low_val
    r2 = pp + (high_val - low_val)
    r3 = high_val + 2 * (pp - low_val)
    s1 = 2 * pp - high_val
    s2 = pp - (high_val - low_val)
    s3 = low_val - 2 * (high_val - pp)
    return {
        "PP": round(pp, 2),
        "R1": round(r1, 2), "R2": round(r2, 2), "R3": round(r3, 2),
        "S1": round(s1, 2), "S2": round(s2, 2), "S3": round(s3, 2),
    }


# ======================================================
# SIGNAL HELPERS
# ======================================================

def rsi_signal(rsi_val: float, ob=70, os=30) -> str:
    if rsi_val >= ob:
        return "OVERBOUGHT"
    elif rsi_val <= os:
        return "OVERSOLD"
    return "NEUTRAL"


def macd_signal(macd_val: float, signal_val: float, macd_prev: float, signal_prev: float) -> str:
    """Deteksi crossover MACD"""
    if macd_prev <= signal_prev and macd_val > signal_val:
        return "GOLDEN_CROSS"
    elif macd_prev >= signal_prev and macd_val < signal_val:
        return "DEAD_CROSS"
    elif macd_val > signal_val:
        return "BULLISH"
    return "BEARISH"


def bb_signal(price: float, upper: float, lower: float, middle: float) -> str:
    if price >= upper:
        return "OVERBOUGHT"
    elif price <= lower:
        return "OVERSOLD"
    elif price > middle:
        return "BULLISH"
    return "BEARISH"


def adx_signal(adx_val: float, plus_di: float, minus_di: float) -> str:
    if adx_val < 20:
        return "SIDEWAYS"
    elif adx_val >= 25 and plus_di > minus_di:
        return "STRONG_UPTREND"
    elif adx_val >= 25 and minus_di > plus_di:
        return "STRONG_DOWNTREND"
    elif plus_di > minus_di:
        return "WEAK_UPTREND"
    return "WEAK_DOWNTREND"
