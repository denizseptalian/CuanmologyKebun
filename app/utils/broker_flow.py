import pandas as pd
import numpy as np


def calc_flow_from_price(df_price, days: int = 60):
    """
    Hitung estimasi aliran asing (institusi) vs retail dari data OHLCV.

    Metodologi Smart Volume Flow:
    - Asing/Institusi: volume yang masuk saat harga tutup di atas 50% range
      (pola akumulasi big player — beli di bawah, tutup di atas tengah bar)
    - Retail: volume yang masuk saat harga tutup di bawah 50% range
      (distribusi / panic sell / momentum ekor bawah)

    Returns
    -------
    DataFrame kolom: date, asing_flow, retail_flow, net_asing, net_retail,
                     close, volume (dalam satuan asli Rupiah * lembar)
    """
    if df_price is None or df_price.empty:
        return None

    df = df_price.copy()

    # Normalize kolom
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).upper().strip() for c in df.columns]

    needed = {"OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"}
    if not needed.issubset(df.columns):
        return None

    for col in needed:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=list(needed))

    # Ambil N hari terakhir (hari bursa)
    df = df.tail(days).copy()

    if len(df) < 5:
        return None

    # ── Hitung close position dalam range ──────────────────────────
    spread = (df["HIGH"] - df["LOW"]).replace(0, np.nan)
    close_pos = ((df["CLOSE"] - df["LOW"]) / spread).clip(0.0, 1.0).fillna(0.5)

    # Nilai transaksi harian (perkiraan: harga × volume)
    value = df["CLOSE"] * df["VOLUME"]

    # ── Aliran asing/institusi: volume masuk di atas 50% range ──────
    # Makin tinggi close_pos → makin besar porsi institusi yang mengakumulasi
    # Formula: value * close_pos (standar VSA / smart money analysis)
    df["asing_flow"] = (value * close_pos).round(0)

    # ── Aliran retail: volume masuk di bawah 50% range ──────────────
    # Bersifat negatif → menandai tekanan jual / distribusi retail
    df["retail_flow"] = -(value * (1.0 - close_pos)).round(0)

    # Net flow
    df["net_asing"]  = df["asing_flow"]
    df["net_retail"] = df["retail_flow"]

    # ── Buat tanggal ──────────────────────────────────────────────────
    df["date"] = (
        pd.to_datetime(df.index)
        if not isinstance(df.index, pd.DatetimeIndex)
        else df.index
    )
    df["date"] = df["date"].dt.tz_localize(None)

    result = df[["date", "asing_flow", "retail_flow",
                 "net_asing", "net_retail",
                 "CLOSE", "VOLUME"]].copy()
    result = result.rename(columns={"CLOSE": "close", "VOLUME": "volume"})
    result = result.reset_index(drop=True)

    return result


def summarize_flow_from_price(df_flow):
    """
    Hitung ringkasan statistik dari df_flow hasil calc_flow_from_price().
    """
    if df_flow is None or df_flow.empty:
        return {}

    total_asing   = df_flow["asing_flow"].sum()
    total_retail  = df_flow["retail_flow"].sum()   # negatif
    avg_asing     = df_flow["asing_flow"].mean()
    avg_retail    = df_flow["retail_flow"].mean()

    # Trend: bandingkan paruh terakhir vs paruh pertama
    n = max(len(df_flow) // 2, 1)
    first_half = df_flow["asing_flow"].iloc[:n].mean()
    last_half  = df_flow["asing_flow"].iloc[-n:].mean()
    asing_trend_up = last_half > first_half

    # Hari dominan
    asing_dominant_days  = int((df_flow["asing_flow"] > df_flow["asing_flow"].abs().mean()).sum())
    retail_dominant_days = int((df_flow["retail_flow"].abs() > df_flow["retail_flow"].abs().mean()).sum())

    return {
        "total_asing":         total_asing,
        "total_retail":        total_retail,
        "avg_asing":           avg_asing,
        "avg_retail":          avg_retail,
        "asing_trend_up":      asing_trend_up,
        "asing_dominant_days": asing_dominant_days,
        "retail_dominant_days": retail_dominant_days,
        "days":                len(df_flow),
    }
