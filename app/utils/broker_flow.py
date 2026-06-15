import pandas as pd
import numpy as np

# Kode broker IDX: (nama lengkap, tipe, bobot market-share relatif)
IDX_BROKERS = {
    # ── Asing / Foreign ────────────────────────────────────────────────────
    "YU": ("CIMB Securities",              "Asing", 0.170),
    "DB": ("Deutsche Securities",          "Asing", 0.140),
    "BK": ("JP Morgan Securities",         "Asing", 0.120),
    "MS": ("Morgan Stanley",               "Asing", 0.110),
    "CS": ("Credit Suisse",                "Asing", 0.090),
    "KI": ("Citigroup Securities",         "Asing", 0.085),
    "UB": ("UBS Securities",               "Asing", 0.075),
    "RX": ("Macquarie Capital",            "Asing", 0.065),
    "ZP": ("Maybank Kim Eng",              "Asing", 0.080),
    "MG": ("Merrill Lynch",                "Asing", 0.075),
    "DP": ("Danareksa Sekuritas",          "Asing", 0.060),
    "AK": ("UBS Securities (2nd)",         "Asing", 0.030),
    # ── Lokal Institusi ─────────────────────────────────────────────────────
    "AZ": ("Mirae Asset Sekuritas",        "Lokal", 0.155),
    "AI": ("Sinarmas Sekuritas",           "Lokal", 0.130),
    "DH": ("Mandiri Sekuritas",            "Lokal", 0.125),
    "XC": ("BCA Sekuritas",                "Lokal", 0.120),
    "PD": ("Indo Premier Sekuritas",       "Lokal", 0.110),
    "NI": ("BNI Sekuritas",                "Lokal", 0.100),
    "EL": ("Trimegah Sekuritas",           "Lokal", 0.090),
    "GR": ("Panin Sekuritas",              "Lokal", 0.080),
    "CP": ("Valbury Asia",                 "Lokal", 0.075),
    "OD": ("Bahana Sekuritas",             "Lokal", 0.065),
    "LS": ("Surya Fajar Capital",          "Lokal", 0.060),
    "DX": ("Phillip Sekuritas",            "Lokal", 0.055),
    "YP": ("Henan Putihrai",               "Lokal", 0.050),
    "KZ": ("CLSA Indonesia",               "Lokal", 0.045),
}


def calc_per_broker_from_price(df_price, days: int = 60, stock_code: str = ""):
    """
    Estimasi aktivitas per kode broker IDX berdasarkan VSA flow.

    Metodologi:
    - Total flow institusi/retail dihitung via VSA dari OHLCV
    - Dibagikan ke kode broker IDX nyata sesuai bobot market-share historis
    - avg_buy / avg_sell dihitung dari VWAP sesi Tier A (institusi) vs Tier C (retail)
    - Seed dari kode saham → hasil konsisten per saham, berbeda antar saham

    CATATAN: Ini adalah estimasi pola, bukan data transaksi broker sesungguhnya.
    """
    df_tiers = calc_broker_tiers_from_price(df_price, days=days)
    if df_tiers is None:
        return None

    # ── VWAP per tier (harga rata-rata tertimbang volume per kelompok sesi) ──
    def _vwap(mask):
        sub = df_tiers[mask]
        if sub.empty or sub["volume"].sum() == 0:
            return df_tiers["close"].mean()
        return (sub["close"] * sub["volume"]).sum() / sub["volume"].sum()

    vwap_a   = _vwap(df_tiers["tier"] == "A")   # sesi institusi/asing
    vwap_b   = _vwap(df_tiers["tier"] == "B")   # sesi mid/fund
    vwap_c   = _vwap(df_tiers["tier"] == "C")   # sesi retail
    vwap_all = _vwap(pd.Series([True] * len(df_tiers), index=df_tiers.index))

    inst_flow   = df_tiers["tier_a_value"].sum() + df_tiers["tier_b_value"].sum() * 0.40
    retail_flow = abs(df_tiers["tier_c_value"].sum()) + df_tiers["tier_b_value"].sum() * 0.60

    seed = abs(hash(stock_code.upper())) % (2 ** 31) if stock_code else 42
    rng  = np.random.default_rng(seed)

    asing_codes = {k: v for k, v in IDX_BROKERS.items() if v[1] == "Asing"}
    lokal_codes = {k: v for k, v in IDX_BROKERS.items() if v[1] == "Lokal"}
    asing_total_w = sum(v[2] for v in asing_codes.values())
    lokal_total_w = sum(v[2] for v in lokal_codes.values())

    rows = []
    for code, (name, broker_type, base_w) in IDX_BROKERS.items():
        noise = rng.uniform(0.55, 1.45)
        adj_w = base_w * noise

        if broker_type == "Asing":
            norm_w = adj_w / asing_total_w
            buy    = inst_flow   * norm_w * 0.70
            sell   = retail_flow * norm_w * 0.22
            # Asing beli di sesi institusi (Tier A) → avg beli ≈ VWAP_A
            # Asing jual di sesi retail (Tier C)   → avg jual ≈ VWAP_C
            avg_buy  = vwap_a * rng.uniform(0.975, 1.025)
            avg_sell = vwap_c * rng.uniform(0.975, 1.025)
        else:
            norm_w = adj_w / lokal_total_w
            buy    = inst_flow   * norm_w * 0.42
            sell   = retail_flow * norm_w * 0.52
            # Lokal lebih banyak di sesi B/C
            avg_buy  = vwap_b * rng.uniform(0.975, 1.025)
            avg_sell = vwap_c * rng.uniform(0.975, 1.025)

        net = buy - sell
        # Harga rata-rata keseluruhan (weighted avg buy+sell volume)
        total_val = buy + sell
        avg_price = (avg_buy * buy + avg_sell * sell) / total_val if total_val > 0 else vwap_all

        rows.append({
            "code":      code,
            "name":      name,
            "type":      broker_type,
            "buy":       round(buy),
            "sell":      round(sell),
            "net":       round(net),
            "avg_buy":   round(avg_buy),
            "avg_sell":  round(avg_sell),
            "avg_price": round(avg_price),
        })

    df_br = pd.DataFrame(rows)
    df_br = df_br.sort_values("net", ascending=False).reset_index(drop=True)
    return df_br


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


def calc_broker_tiers_from_price(df_price, days: int = 60):
    """
    Klasifikasi sesi trading ke dalam 3 tier broker berdasarkan VSA:
      - Tier A (Institusi/Asing): volume tinggi + close tutup di atas 60% range
      - Tier B (Dana Reksa/Mid): volume sedang + close di tengah range
      - Tier C (Retail/Domestik): volume rendah atau close di bawah 40% range

    Tidak menggunakan data broker IDX — semua dihitung dari OHLCV.
    """
    if df_price is None or df_price.empty:
        return None

    df = df_price.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).upper().strip() for c in df.columns]

    needed = {"OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"}
    if not needed.issubset(df.columns):
        return None

    for col in needed:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=list(needed)).tail(days).copy()
    if len(df) < 5:
        return None

    spread = (df["HIGH"] - df["LOW"]).replace(0, np.nan)
    close_pos = ((df["CLOSE"] - df["LOW"]) / spread).clip(0.0, 1.0).fillna(0.5)
    value = df["CLOSE"] * df["VOLUME"]

    vol_mean = df["VOLUME"].mean()
    vol_high = vol_mean * 1.4
    vol_low  = vol_mean * 0.65

    # Tier A — institusi/asing: volume besar + close dekat top bar
    tier_a_mask = (df["VOLUME"] >= vol_high) & (close_pos >= 0.60)
    # Tier C — retail: volume kecil ATAU close di bawah 40%
    tier_c_mask = (df["VOLUME"] <= vol_low) | (close_pos < 0.40)
    # Tier B — sisanya
    tier_b_mask = ~tier_a_mask & ~tier_c_mask

    df["tier_a_value"] = np.where(tier_a_mask, value * close_pos, 0.0)
    df["tier_b_value"] = np.where(tier_b_mask, value * 0.5, 0.0)
    df["tier_c_value"] = np.where(tier_c_mask, -(value * (1.0 - close_pos)), 0.0)
    df["tier"]         = np.where(tier_a_mask, "A",
                         np.where(tier_b_mask, "B", "C"))

    df["date"] = (
        pd.to_datetime(df.index)
        if not isinstance(df.index, pd.DatetimeIndex)
        else df.index
    )
    df["date"] = df["date"].dt.tz_localize(None)

    result = df[["date", "CLOSE", "VOLUME",
                 "tier", "tier_a_value", "tier_b_value", "tier_c_value"]].copy()
    result = result.rename(columns={"CLOSE": "close", "VOLUME": "volume"})
    result = result.reset_index(drop=True)
    return result


def summarize_broker_tiers(df_tiers):
    """Ringkasan statistik tier broker."""
    if df_tiers is None or df_tiers.empty:
        return {}

    total_days = len(df_tiers)
    a_days = int((df_tiers["tier"] == "A").sum())
    b_days = int((df_tiers["tier"] == "B").sum())
    c_days = int((df_tiers["tier"] == "C").sum())

    return {
        "total_days": total_days,
        "tier_a_days": a_days,
        "tier_b_days": b_days,
        "tier_c_days": c_days,
        "tier_a_total": df_tiers["tier_a_value"].sum(),
        "tier_b_total": df_tiers["tier_b_value"].sum(),
        "tier_c_total": df_tiers["tier_c_value"].sum(),
        "tier_a_pct": round(a_days / total_days * 100, 1),
        "tier_b_pct": round(b_days / total_days * 100, 1),
        "tier_c_pct": round(c_days / total_days * 100, 1),
    }


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
