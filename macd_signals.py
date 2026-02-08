import yfinance as yf
import pandas as pd
import numpy as np

# =========================
# Utility helpers
# =========================

def to_1d(x):
    arr = np.asarray(x)
    return arr.reshape(-1)


def colored_output(action):
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'

    return {
        "Buy": f"{GREEN}{action}{RESET}",
        "Hold": f"{YELLOW}{action}{RESET}",
        "Sell": f"{RED}{action}{RESET}",
        "Wait for Buy": f"{MAGENTA}{action}{RESET}",
    }.get(action, action)


# =========================
# Impulse MACD helpers
# =========================

def calc_smma(src, length):
    """
    Smoothed Moving Average (RMA/SMMA in Pine Script)
    Uses pandas for cleaner implementation
    """
    src = to_1d(src)
    
    if len(src) < length:
        return np.full(len(src), np.nan)
    
    # Use pandas ewm with alpha = 1/length (equivalent to SMMA)
    alpha = 1.0 / length
    smma = pd.Series(src).ewm(alpha=alpha, adjust=False).mean().values
    
    return smma


def calc_zlema(src, length):
    """
    ZLEMA as implemented by LazyBear (DEMA variant)
    """
    src = to_1d(src)
    ema1 = pd.Series(src).ewm(span=length, adjust=False).mean().values
    ema2 = pd.Series(ema1).ewm(span=length, adjust=False).mean().values
    d = ema1 - ema2
    return ema1 + d


# =========================
# Trend → Action
# =========================

def _trend_to_action(trend_series):
    action_list = []
    last_trend = None
    
    for trend in trend_series:
        if trend == "B":
            action_list.append("Buy")
            last_trend = "Bullish"
        elif trend == "S":
            action_list.append("Sell")
            last_trend = "Bearish"
        else:
            if last_trend == "Bullish":
                action_list.append("Hold")
            elif last_trend == "Bearish":
                action_list.append("Wait for Buy")
            else:
                action_list.append("Hold")

    return action_list[-1] if action_list else "Hold"


# =========================
# Standard MACD
# =========================

def calculate_macd(df):
    if df.empty or len(df) < 2:
        return "Hold"

    close = to_1d(df["Close"])

    ema_12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema_26 = pd.Series(close).ewm(span=26, adjust=False).mean().values

    macd_line = ema_12 - ema_26
    signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values

    prev_macd = np.concatenate([[np.nan], macd_line[:-1]])
    prev_signal = np.concatenate([[np.nan], signal_line[:-1]])

    bullish = (prev_macd < prev_signal) & (macd_line > signal_line)
    bearish = (prev_macd > prev_signal) & (macd_line < signal_line)

    trend = np.array([""] * len(close))
    trend[bullish] = "B"
    trend[bearish] = "S"

    return _trend_to_action(trend)


# =========================
# Impulse MACD (LazyBear)
# =========================

def calculate_impulse_macd(df, length_ma=34, length_signal=9):
    if df.empty or len(df) < length_ma + length_signal:
        return "Hold"

    high = to_1d(df["High"])
    low = to_1d(df["Low"])
    close = to_1d(df["Close"])

    src = (high + low + close) / 3

    hi = calc_smma(high, length_ma)
    lo = calc_smma(low, length_ma)
    mi = calc_zlema(src, length_ma)

    # Check for NaN values
    if np.any(np.isnan(hi)) or np.any(np.isnan(lo)) or np.any(np.isnan(mi)):
        return "Hold"

    # Calculate ImpulseMACD
    md = np.where(mi > hi, mi - hi, np.where(mi < lo, mi - lo, 0))
    
    # Calculate Signal line (SMA of md)
    sb = pd.Series(md).rolling(length_signal).mean().values
    
    # Calculate histogram
    sh = md - sb

    # Detect crossovers based on MD crossing SB
    prev_md = np.concatenate([[np.nan], md[:-1]])
    prev_sb = np.concatenate([[np.nan], sb[:-1]])

    bullish = (prev_md < prev_sb) & (md > sb)
    bearish = (prev_md > prev_sb) & (md < sb)

    trend = np.array([""] * len(md))
    trend[bullish] = "B"
    trend[bearish] = "S"

    return _trend_to_action(trend)


# =========================
# Process signals from pre-downloaded data
# =========================

def process_both_signals(data, stocks):
    """
    Process MACD signals from pre-downloaded data
    
    Args:
        data: Pre-downloaded yfinance data (MultiIndex DataFrame)
        stocks: List of stock symbols
    
    Returns:
        Tuple of (macd_actions, impulse_actions) dictionaries
    """
    macd_actions = {}
    impulse_actions = {}

    if data.empty:
        print("Empty dataset provided")
        return macd_actions, impulse_actions

    print(f"\nProcessing MACD signals for {len(stocks)} stocks...")

    for idx, stock in enumerate(stocks, 1):
        try:
            print(f"  [{idx}/{len(stocks)}] {stock}...", end=" ", flush=True)

            if stock not in data.columns.get_level_values(1):
                raise ValueError("No data returned")

            df = data.xs(stock, axis=1, level=1)

            # Clean data: remove rows with NaN values
            df = df.dropna()

            if df.empty or len(df) < 50:
                raise ValueError(f"Insufficient data (only {len(df)} bars)")

            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
            else:
                df.index = df.index.tz_convert("Asia/Kolkata")

            macd_actions[stock] = {
                "action": calculate_macd(df),
                "time": df.index[-1],
                "price": float(df["Close"].iloc[-1]),
            }

            impulse_actions[stock] = {
                "action": calculate_impulse_macd(df),
                "time": df.index[-1],
                "price": float(df["Close"].iloc[-1]),
            }

            print("✓")

        except Exception as e:
            print(f"✗ ({str(e)[:60]})")

    return macd_actions, impulse_actions


# =========================
# LEGACY: Data fetch + process
# =========================

def fetch_both_signals(stocks, interval):
    """LEGACY: Downloads data and calculates signals. Use process_both_signals with pre-downloaded data instead."""
    print(f"\nDownloading {len(stocks)} symbols in one batch...")

    data = yf.download(
        stocks,
        period="90d",
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if data.empty:
        print("Download failed: empty dataset")
        return {}, {}

    return process_both_signals(data, stocks)


# =========================
# Main
# =========================

if __name__ == "__main__":
    try:
        with open("stocks.txt", "r") as f:
            stocks = [line.strip() + ".NS" for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: stocks.txt not found")
        exit(1)

    interval = "1d"

    print(f"Fetching MACD signals for interval: {interval}")

    results_macd, results_impulse = fetch_both_signals(stocks, interval)

    print("\n" + "=" * 60)
    print("STANDARD MACD")
    print("=" * 60)
    for stock, info in results_macd.items():
        print(f"{stock} @ ₹{info['price']:.2f}: {colored_output(info['action'])}")

    print("\n" + "=" * 60)
    print("IMPULSE MACD (LazyBear)")
    print("=" * 60)
    for stock, info in results_impulse.items():
        print(f"{stock} @ ₹{info['price']:.2f}: {colored_output(info['action'])}")
