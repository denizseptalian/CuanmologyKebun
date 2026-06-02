"""
Multi-Algorithm Screener
Screener fleksibel yang menggabungkan berbagai algoritma teknikal.
Setiap algoritma memberikan sinyal, lalu digabungkan menjadi skor akhir.
"""

import pandas as pd
import numpy as np
from app.core.data_loader import load_daily_data
from app.core.indicators import (
    ema, sma, rsi, macd,
    bollinger_bands, bollinger_pct_b, bollinger_bandwidth,
    atr, stochastic_rsi, stochastic, adx, supertrend,
    obv, williams_r, cci, mfi,
    rsi_signal, macd_signal, bb_signal, adx_signal,
)
from app.utils.helpers import round_down, round_up


# ============================================================
# KONFIGURASI DEFAULT
# ============================================================

DEFAULT_CONFIG = {
    # Algoritma yang aktif (True/False)
    "use_rsi":          True,
    "use_macd":         True,
    "use_bb":           True,
    "use_ema_cross":    True,
    "use_adx":          True,
    "use_supertrend":   True,
    "use_stoch_rsi":    True,
    "use_obv":          True,
    "use_mfi":          False,
    "use_cci":          False,
    "use_williams_r":   False,

    # Parameter RSI
    "rsi_period":       14,
    "rsi_ob":           70,
    "rsi_os":           30,

    # Parameter MACD
    "macd_fast":        12,
    "macd_slow":        26,
    "macd_signal":      9,

    # Parameter Bollinger Bands
    "bb_period":        20,
    "bb_std":           2.0,

    # Parameter EMA Cross
    "ema_fast":         9,
    "ema_slow":         21,

    # Parameter ADX
    "adx_period":       14,
    "adx_threshold":    25,

    # Parameter Supertrend
    "st_period":        10,
    "st_multiplier":    3.0,

    # Parameter Stochastic RSI
    "srsi_rsi_period":  14,
    "srsi_stoch_period": 14,
    "srsi_smooth_k":    3,
    "srsi_smooth_d":    3,
    "srsi_ob":          80,
    "srsi_os":          20,

    # Parameter OBV
    "obv_ma_period":    20,

    # Parameter MFI
    "mfi_period":       14,
    "mfi_ob":           80,
    "mfi_os":           20,

    # Parameter CCI
    "cci_period":       20,

    # Parameter Williams %R
    "wr_period":        14,

    # Filter dasar
    "min_volume":       1_000_000,
    "min_score":        50,
    "data_period":      "6mo",
}


# ============================================================
# ANALYZER UTAMA
# ============================================================

def analyze_multi_algo(kode: str, config: dict = None) -> dict | None:
    """
    Analisis satu saham dengan kombinasi algoritma yang dikonfigurasi.
    Mengembalikan dict hasil atau None jika tidak memenuhi syarat.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    df = load_daily_data(kode, period=cfg["data_period"])

    if df is None or len(df) < 60:
        return None

    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]
    open_ = df["Open"]

    # Filter volume minimum
    avg_vol = vol.tail(20).mean()
    if avg_vol < cfg["min_volume"]:
        return None

    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    last_vol   = float(vol.iloc[-1])

    signals = {}
    scores  = {}
    total_weight = 0
    total_score  = 0

    # --------------------------------------------------------
    # 1. RSI
    # --------------------------------------------------------
    if cfg["use_rsi"]:
        rsi_vals = rsi(close, cfg["rsi_period"])
        rsi_now  = float(rsi_vals.iloc[-1])
        rsi_prev = float(rsi_vals.iloc[-2])
        sig = rsi_signal(rsi_now, cfg["rsi_ob"], cfg["rsi_os"])

        if sig == "OVERSOLD":
            sc = 80
        elif sig == "NEUTRAL" and rsi_now > 50 and rsi_now > rsi_prev:
            sc = 65
        elif sig == "NEUTRAL" and rsi_now < 50:
            sc = 35
        else:
            sc = 20   # overbought → jangan beli terlambat

        signals["RSI"] = {
            "value": round(rsi_now, 1),
            "signal": sig,
            "score": sc
        }
        scores["RSI"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 2. MACD
    # --------------------------------------------------------
    if cfg["use_macd"]:
        ml, sl_line, hist = macd(
            close, cfg["macd_fast"], cfg["macd_slow"], cfg["macd_signal"]
        )
        ml_now    = float(ml.iloc[-1])
        sl_now    = float(sl_line.iloc[-1])
        ml_prev   = float(ml.iloc[-2])
        sl_prev   = float(sl_line.iloc[-2])
        hist_now  = float(hist.iloc[-1])
        sig = macd_signal(ml_now, sl_now, ml_prev, sl_prev)

        if sig == "GOLDEN_CROSS":
            sc = 90
        elif sig == "BULLISH" and hist_now > 0:
            sc = 65
        elif sig == "DEAD_CROSS":
            sc = 10
        else:
            sc = 35

        signals["MACD"] = {
            "value": round(ml_now, 4),
            "histogram": round(hist_now, 4),
            "signal": sig,
            "score": sc
        }
        scores["MACD"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 3. Bollinger Bands
    # --------------------------------------------------------
    if cfg["use_bb"]:
        upper, middle, lower = bollinger_bands(close, cfg["bb_period"], cfg["bb_std"])
        u, m, l = float(upper.iloc[-1]), float(middle.iloc[-1]), float(lower.iloc[-1])
        pct_b   = float(bollinger_pct_b(close, cfg["bb_period"], cfg["bb_std"]).iloc[-1])
        bw      = float(bollinger_bandwidth(close, cfg["bb_period"], cfg["bb_std"]).iloc[-1])
        sig     = bb_signal(last_close, u, m, l)

        if sig == "OVERSOLD":
            sc = 80
        elif sig == "BULLISH" and pct_b < 0.8:
            sc = 60
        elif sig == "OVERBOUGHT":
            sc = 20
        else:
            sc = 40

        # Bonus: squeeze (bandwidth rendah) → breakout akan datang
        avg_bw = float(bollinger_bandwidth(close, cfg["bb_period"], cfg["bb_std"]).tail(20).mean())
        if bw < avg_bw * 0.7:
            sc = min(sc + 15, 100)
            sig += " + SQUEEZE"

        signals["Bollinger Bands"] = {
            "upper": round(u, 0),
            "middle": round(m, 0),
            "lower": round(l, 0),
            "%B": round(pct_b, 2),
            "bandwidth": round(bw, 4),
            "signal": sig,
            "score": sc
        }
        scores["BB"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 4. EMA Cross
    # --------------------------------------------------------
    if cfg["use_ema_cross"]:
        ema_fast_line = ema(close, cfg["ema_fast"])
        ema_slow_line = ema(close, cfg["ema_slow"])
        ef_now  = float(ema_fast_line.iloc[-1])
        es_now  = float(ema_slow_line.iloc[-1])
        ef_prev = float(ema_fast_line.iloc[-2])
        es_prev = float(ema_slow_line.iloc[-2])

        golden = ef_prev <= es_prev and ef_now > es_now
        dead   = ef_prev >= es_prev and ef_now < es_now
        above  = ef_now > es_now

        if golden:
            sig, sc = "GOLDEN_CROSS", 90
        elif dead:
            sig, sc = "DEAD_CROSS", 10
        elif above:
            sig, sc = "BULLISH", 65
        else:
            sig, sc = "BEARISH", 30

        signals["EMA Cross"] = {
            f"EMA{cfg['ema_fast']}": round(ef_now, 0),
            f"EMA{cfg['ema_slow']}": round(es_now, 0),
            "signal": sig,
            "score": sc
        }
        scores["EMA_Cross"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 5. ADX
    # --------------------------------------------------------
    if cfg["use_adx"]:
        adx_val, pdi, mdi = adx(high, low, close, cfg["adx_period"])
        adx_now = float(adx_val.iloc[-1])
        pdi_now = float(pdi.iloc[-1])
        mdi_now = float(mdi.iloc[-1])
        sig = adx_signal(adx_now, pdi_now, mdi_now)

        if sig == "STRONG_UPTREND":
            sc = 85
        elif sig == "WEAK_UPTREND":
            sc = 60
        elif sig == "SIDEWAYS":
            sc = 40
        elif sig == "WEAK_DOWNTREND":
            sc = 30
        else:
            sc = 15

        signals["ADX"] = {
            "adx": round(adx_now, 1),
            "+DI": round(pdi_now, 1),
            "-DI": round(mdi_now, 1),
            "signal": sig,
            "score": sc
        }
        scores["ADX"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 6. Supertrend
    # --------------------------------------------------------
    if cfg["use_supertrend"]:
        st_line, direction = supertrend(
            high, low, close, cfg["st_period"], cfg["st_multiplier"]
        )
        dir_now  = int(direction.iloc[-1])
        dir_prev = int(direction.iloc[-2])
        st_now   = float(st_line.iloc[-1]) if not np.isnan(st_line.iloc[-1]) else 0

        if dir_prev == -1 and dir_now == 1:
            sig, sc = "BUY_SIGNAL", 90
        elif dir_prev == 1 and dir_now == -1:
            sig, sc = "SELL_SIGNAL", 10
        elif dir_now == 1:
            sig, sc = "UPTREND", 70
        else:
            sig, sc = "DOWNTREND", 25

        signals["Supertrend"] = {
            "value": round(st_now, 0),
            "direction": dir_now,
            "signal": sig,
            "score": sc
        }
        scores["Supertrend"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 7. Stochastic RSI
    # --------------------------------------------------------
    if cfg["use_stoch_rsi"]:
        k, d = stochastic_rsi(
            close,
            cfg["srsi_rsi_period"],
            cfg["srsi_stoch_period"],
            cfg["srsi_smooth_k"],
            cfg["srsi_smooth_d"]
        )
        k_now, d_now = float(k.iloc[-1]), float(d.iloc[-1])
        k_prev, d_prev = float(k.iloc[-2]), float(d.iloc[-2])

        cross_up   = k_prev <= d_prev and k_now > d_now
        cross_down = k_prev >= d_prev and k_now < d_now

        if k_now < cfg["srsi_os"] and cross_up:
            sig, sc = "OVERSOLD_CROSS", 90
        elif k_now > cfg["srsi_ob"] and cross_down:
            sig, sc = "OVERBOUGHT_CROSS", 10
        elif k_now < cfg["srsi_os"]:
            sig, sc = "OVERSOLD", 70
        elif k_now > cfg["srsi_ob"]:
            sig, sc = "OVERBOUGHT", 20
        elif k_now > d_now:
            sig, sc = "BULLISH", 60
        else:
            sig, sc = "BEARISH", 35

        signals["Stoch RSI"] = {
            "%K": round(k_now, 1),
            "%D": round(d_now, 1),
            "signal": sig,
            "score": sc
        }
        scores["StochRSI"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 8. OBV
    # --------------------------------------------------------
    if cfg["use_obv"]:
        obv_vals = obv(close, vol)
        obv_ma   = obv_vals.rolling(cfg["obv_ma_period"]).mean()
        obv_now  = float(obv_vals.iloc[-1])
        obv_ma_now = float(obv_ma.iloc[-1])
        obv_prev = float(obv_vals.iloc[-2])

        rising_price = last_close > prev_close
        rising_obv   = obv_now > obv_prev
        obv_above_ma = obv_now > obv_ma_now

        if rising_price and rising_obv and obv_above_ma:
            sig, sc = "STRONG_ACCUMULATION", 85
        elif rising_obv and not rising_price:
            sig, sc = "HIDDEN_ACCUMULATION", 75
        elif not rising_obv and rising_price:
            sig, sc = "DIVERGENCE_WARNING", 30
        elif not rising_obv:
            sig, sc = "DISTRIBUTION", 20
        else:
            sig, sc = "NEUTRAL", 50

        signals["OBV"] = {
            "obv": round(obv_now, 0),
            "signal": sig,
            "score": sc
        }
        scores["OBV"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 9. MFI (Money Flow Index)
    # --------------------------------------------------------
    if cfg["use_mfi"]:
        mfi_vals = mfi(high, low, close, vol, cfg["mfi_period"])
        mfi_now  = float(mfi_vals.iloc[-1])

        if mfi_now <= cfg["mfi_os"]:
            sig, sc = "OVERSOLD", 80
        elif mfi_now >= cfg["mfi_ob"]:
            sig, sc = "OVERBOUGHT", 20
        elif mfi_now > 50:
            sig, sc = "BULLISH", 65
        else:
            sig, sc = "BEARISH", 35

        signals["MFI"] = {
            "value": round(mfi_now, 1),
            "signal": sig,
            "score": sc
        }
        scores["MFI"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 10. CCI
    # --------------------------------------------------------
    if cfg["use_cci"]:
        cci_vals = cci(high, low, close, cfg["cci_period"])
        cci_now  = float(cci_vals.iloc[-1])

        if cci_now <= -100:
            sig, sc = "OVERSOLD", 80
        elif cci_now >= 100:
            sig, sc = "OVERBOUGHT", 20
        elif cci_now > 0:
            sig, sc = "BULLISH", 60
        else:
            sig, sc = "BEARISH", 35

        signals["CCI"] = {
            "value": round(cci_now, 1),
            "signal": sig,
            "score": sc
        }
        scores["CCI"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # 11. Williams %R
    # --------------------------------------------------------
    if cfg["use_williams_r"]:
        wr_vals = williams_r(high, low, close, cfg["wr_period"])
        wr_now  = float(wr_vals.iloc[-1])

        if wr_now <= -80:
            sig, sc = "OVERSOLD", 80
        elif wr_now >= -20:
            sig, sc = "OVERBOUGHT", 20
        elif wr_now > -50:
            sig, sc = "BULLISH", 60
        else:
            sig, sc = "BEARISH", 35

        signals["Williams %R"] = {
            "value": round(wr_now, 1),
            "signal": sig,
            "score": sc
        }
        scores["Williams_R"] = sc
        total_weight += 1
        total_score  += sc

    # --------------------------------------------------------
    # HITUNG SKOR AKHIR
    # --------------------------------------------------------
    if total_weight == 0:
        return None

    final_score = int(total_score / total_weight)

    if final_score < cfg["min_score"]:
        return None

    # --------------------------------------------------------
    # REKOMENDASI
    # --------------------------------------------------------
    if final_score >= 80:
        recommendation = "STRONG BUY"
        emoji = "🔥"
    elif final_score >= 65:
        recommendation = "BUY"
        emoji = "✅"
    elif final_score >= 50:
        recommendation = "WATCH"
        emoji = "👀"
    else:
        recommendation = "AVOID"
        emoji = "⚠️"

    # --------------------------------------------------------
    # KALKULASI ENTRY / TP / SL
    # --------------------------------------------------------
    atr_val_now = float(atr(high, low, close).iloc[-1])

    entry = round_down(last_close)
    sl    = round_down(last_close - 2 * atr_val_now)
    tp1   = round_up(last_close + 1.5 * atr_val_now)
    tp2   = round_up(last_close + 3.0 * atr_val_now)
    tp3   = round_up(last_close + 5.0 * atr_val_now)

    risk   = max(last_close - sl, 1)
    reward = tp2 - last_close
    rr     = round(reward / risk, 2)

    # Volume ratio untuk konteks
    vol_avg = float(vol.tail(20).mean())
    vol_ratio = round(last_vol / vol_avg, 2) if vol_avg > 0 else 0

    return {
        "kode":           kode,
        "price":          entry,
        "score":          final_score,
        "recommendation": f"{emoji} {recommendation}",
        "signals":        signals,
        "scores":         scores,
        "entry":          entry,
        "sl":             sl,
        "tp1":            tp1,
        "tp2":            tp2,
        "tp3":            tp3,
        "rr":             rr,
        "atr":            round(atr_val_now, 0),
        "vol_ratio":      vol_ratio,
        "active_algos":   total_weight,
    }


# ============================================================
# BATCH SCAN
# ============================================================

def scan_multi_algo(saham_list: list, config: dict = None) -> list:
    """
    Scan banyak saham dengan konfigurasi algoritma yang dipilih.
    Mengembalikan list hasil yang sudah difilter dan diurutkan.
    """
    results = []
    for kode in saham_list:
        try:
            result = analyze_multi_algo(kode, config)
            if result:
                results.append(result)
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
