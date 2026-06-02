import numpy as np
import pandas as pd


# ==========================================================
# 📉 MINOR SUPPORT
# ==========================================================
def calc_minor_support(df, lookback=12):
    try:
        if df is None:
            return None

        recent = df.tail(lookback)

        # Flatten MultiIndex jadi satu level dengan label "field ticker"
        if isinstance(recent.columns, pd.MultiIndex):
            cols = pd.Index([str(c[0]).lower() for c in recent.columns])
        else:
            cols = pd.Index([str(c).lower() for c in recent.columns])

        if "low" not in cols:
            return None

        idx = cols.get_loc("low")
        raw = recent.iloc[:, idx]

        vals = []
        for v in raw:
            try:
                f = float(v)
                if not np.isnan(f):
                    vals.append(f)
            except Exception:
                pass

        return min(vals) if vals else None
    except Exception:
        return None


# ==========================================================
# 🧼 CLEAN PRICE DATA
# ==========================================================
def clean_price_df(df):

    if df is None:
        return None

    df = df.copy()

    # ===== FLATTEN MULTI INDEX =====
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(col).upper() for col in df.columns]
    else:
        df.columns = [str(c).upper().strip() for c in df.columns]

    # ===== NORMALIZE OHLC =====
    col_map = {}

    for col in df.columns:
        c = col.upper()

        if "OPEN" in c:
            col_map[col] = "OPEN"
        elif "HIGH" in c:
            col_map[col] = "HIGH"
        elif "LOW" in c:
            col_map[col] = "LOW"
        elif "CLOSE" in c:
            col_map[col] = "CLOSE"

    df = df.rename(columns=col_map)

    # ===== VALIDATE =====
    if "CLOSE" not in df.columns:
        return None

    # ===== NUMERIC =====
    for col in ["OPEN", "HIGH", "LOW", "CLOSE"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["CLOSE"])
    df = df.sort_index()

    return df

# ==========================================================
# 💰 FORMAT MONEY
# ==========================================================
def format_money(x):
    """
    Convert number → human readable:
    1,000,000 → 1.00 M
    """
    if pd.isna(x):
        return "-"

    x = float(x)
    sign = "-" if x < 0 else ""
    x = abs(x)

    if x >= 1_000_000_000_000:
        return f"{sign}{x/1_000_000_000_000:.2f} T"
    elif x >= 1_000_000_000:
        return f"{sign}{x/1_000_000_000:.2f} B"
    elif x >= 1_000_000:
        return f"{sign}{x/1_000_000:.2f} M"
    else:
        return f"{sign}{int(x):,}".replace(",", ".")


# ==========================================================
# 🔢 FORMAT NUMBER
# ==========================================================
def format_number(x):
    """
    Format angka biasa:
    1000000 → 1.000.000
    """
    try:
        return f"{int(x):,}".replace(",", ".")
    except:
        return "-"