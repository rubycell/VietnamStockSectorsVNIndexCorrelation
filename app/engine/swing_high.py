"""Swing high detection using SMA crossover (inverse of swing low).

Algorithm:
1. Compute SMA(close, period)
2. Find Point A: candle where close > SMA
3. Find Point B: next candle where close < SMA AND high < SMA
4. Swing high = MAX(high) from A to B inclusive
5. Confirmed when Point B is found

Active swing highs are invalidated when a candle closes above them.
"""

import pandas as pd


def detect_swing_highs(
    ohlcv: pd.DataFrame,
    sma_period: int = 10,
) -> list[dict]:
    """Detect swing highs in OHLCV data.

    Args:
        ohlcv: DataFrame with columns: date, open, high, low, close, volume
        sma_period: Period for SMA calculation (default 10)

    Returns:
        List of dicts with: date, price, confirmed, point_a_date, point_b_date
    """
    if len(ohlcv) < sma_period + 1:
        return []

    df = ohlcv.copy()
    df = df.sort_values("date").reset_index(drop=True)
    df["sma"] = df["close"].rolling(window=sma_period).mean()

    swing_highs = []
    in_rise = False
    point_a_idx = None

    for i in range(sma_period, len(df)):
        sma_val = df.loc[i, "sma"]
        close_val = df.loc[i, "close"]
        high_val = df.loc[i, "high"]

        if pd.isna(sma_val):
            continue

        if not in_rise:
            # Point A: close crosses above SMA
            if close_val > sma_val:
                in_rise = True
                point_a_idx = i
        else:
            # Point B: close drops back below SMA AND high < SMA
            if close_val < sma_val and high_val < sma_val:
                rise_range = df.loc[point_a_idx:i]
                max_high_idx = rise_range["high"].idxmax()

                swing_highs.append({
                    "date": df.loc[max_high_idx, "date"],
                    "price": df.loc[max_high_idx, "high"],
                    "confirmed": True,
                    "point_a_date": df.loc[point_a_idx, "date"],
                    "point_b_date": df.loc[i, "date"],
                })

                in_rise = False
                point_a_idx = None

    # If still in a rise at the end, record unconfirmed swing high
    if in_rise and point_a_idx is not None:
        rise_range = df.loc[point_a_idx:]
        max_high_idx = rise_range["high"].idxmax()

        swing_highs.append({
            "date": df.loc[max_high_idx, "date"],
            "price": df.loc[max_high_idx, "high"],
            "confirmed": False,
            "point_a_date": df.loc[point_a_idx, "date"],
            "point_b_date": None,
        })

    return swing_highs


def filter_active_swing_highs(
    swing_highs: list[dict],
    ohlcv: pd.DataFrame,
) -> list[dict]:
    """Remove swing highs that have been invalidated by price closing above them.

    A swing high is invalidated when any candle AFTER it closes above its price.
    """
    if not swing_highs or ohlcv.empty:
        return swing_highs

    df = ohlcv.copy().sort_values("date").reset_index(drop=True)
    active = []

    for swing_high in swing_highs:
        swing_date = swing_high["date"]
        swing_price = swing_high["price"]

        # Get candles after the swing high date
        later_candles = df[df["date"] > swing_date]

        # Check if any candle closed above this swing high
        invalidated = (later_candles["close"] > swing_price).any()

        if not invalidated:
            active.append(swing_high)

    return active
