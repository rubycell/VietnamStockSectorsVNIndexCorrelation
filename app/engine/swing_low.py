"""Swing low detection using custom SMA(10) algorithm.

Algorithm:
1. Compute SMA(close, period)
2. Find Point A: candle where close < SMA
3. Find Point B: next candle where close > SMA AND low > SMA
4. Swing low = MIN(low) from A to B inclusive
5. Confirmed when Point B is found
"""

import pandas as pd


def detect_swing_lows(
    ohlcv: pd.DataFrame,
    sma_period: int = 10,
) -> list[dict]:
    """Detect swing lows in OHLCV data.

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

    swing_lows = []
    in_dip = False
    point_a_idx = None

    for i in range(sma_period, len(df)):
        sma_val = df.loc[i, "sma"]
        close_val = df.loc[i, "close"]
        low_val = df.loc[i, "low"]

        if pd.isna(sma_val):
            continue

        if not in_dip:
            # Look for Point A: close < SMA
            if close_val < sma_val:
                in_dip = True
                point_a_idx = i
        else:
            # Look for Point B: close > SMA AND low > SMA
            if close_val > sma_val and low_val > sma_val:
                # Found Point B — swing low confirmed
                dip_range = df.loc[point_a_idx:i]
                min_low_idx = dip_range["low"].idxmin()

                swing_lows.append({
                    "date": df.loc[min_low_idx, "date"],
                    "price": df.loc[min_low_idx, "low"],
                    "confirmed": True,
                    "point_a_date": df.loc[point_a_idx, "date"],
                    "point_b_date": df.loc[i, "date"],
                })

                in_dip = False
                point_a_idx = None

    # If still in a dip at the end, record unconfirmed swing low
    if in_dip and point_a_idx is not None:
        dip_range = df.loc[point_a_idx:]
        min_low_idx = dip_range["low"].idxmin()

        swing_lows.append({
            "date": df.loc[min_low_idx, "date"],
            "price": df.loc[min_low_idx, "low"],
            "confirmed": False,
            "point_a_date": df.loc[point_a_idx, "date"],
            "point_b_date": None,
        })

    return swing_lows
