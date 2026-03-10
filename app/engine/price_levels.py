"""Important price level detection.

Three sources:
1. Round number levels (5k, 10k VND increments)
2. Resistance zones (swing highs - inverse of swing low)
3. Manual levels (user-configured)
"""

import pandas as pd


def get_round_number_levels(
    current_price: float,
    range_pct: float = 20.0,
) -> list[dict]:
    """Get round number levels near the current price.

    Returns levels at 5,000 and 10,000 VND increments
    within range_pct% of current price.
    """
    low_bound = current_price * (1 - range_pct / 100)
    high_bound = current_price * (1 + range_pct / 100)

    levels = []

    # 5,000 VND increments
    start_5k = int(low_bound / 5000) * 5000
    price = start_5k
    while price <= high_bound:
        if price > 0:
            is_10k = price % 10000 == 0
            levels.append({
                "price": price,
                "level_type": "round",
                "description": f"Round {'10k' if is_10k else '5k'}: {price:,.0f}",
            })
        price += 5000

    return levels


def detect_resistance_zones(
    ohlcv: pd.DataFrame,
    sma_period: int = 10,
) -> list[dict]:
    """Detect resistance zones using swing highs (inverse of swing low).

    Swing high: price rises above SMA, then drops back below SMA.
    Resistance = MAX(high) during the rise period.
    """
    if len(ohlcv) < sma_period + 1:
        return []

    df = ohlcv.copy().sort_values("date").reset_index(drop=True)
    df["sma"] = df["close"].rolling(window=sma_period).mean()

    zones = []
    in_rise = False
    point_a_idx = None

    for i in range(sma_period, len(df)):
        sma_val = df.loc[i, "sma"]
        close_val = df.loc[i, "close"]

        if pd.isna(sma_val):
            continue

        if not in_rise:
            # Point A: close crosses above SMA
            if close_val > sma_val:
                in_rise = True
                point_a_idx = i
        else:
            # Point B: close drops back below SMA
            if close_val < sma_val:
                rise_range = df.loc[point_a_idx:i]
                max_high_idx = rise_range["high"].idxmax()

                zones.append({
                    "price": df.loc[max_high_idx, "high"],
                    "level_type": "resistance",
                    "description": f"Swing high on {df.loc[max_high_idx, 'date']}",
                    "date": df.loc[max_high_idx, "date"],
                })

                in_rise = False
                point_a_idx = None

    return zones


def merge_price_levels(
    round_levels: list[dict],
    resistance_levels: list[dict],
    manual_levels: list[dict],
) -> list[dict]:
    """Merge all price level sources, sorted by price."""
    all_levels = round_levels + resistance_levels + manual_levels
    return sorted(all_levels, key=lambda x: x["price"])
