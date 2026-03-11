"""Important price level detection.

Three sources:
1. Round number levels (configurable increments, default 50k/100k VND)
2. Resistance zones (swing highs - inverse of swing low)
3. Manual levels (user-configured)
"""

import pandas as pd

DEFAULT_INCREMENTS = [50, 100]


def get_round_number_levels(
    current_price: float,
    nearest_count: int = 3,
    increments: list[float] | None = None,
) -> list[dict]:
    """Get round number levels near the current price.

    Finds the nearest N levels above and below for each increment size.
    Prices are in x1000 VND (vnstock convention), so increment=50 means 50,000 VND.

    Args:
        current_price: Current stock price (in x1000 VND, e.g. 23.1 = 23,100 VND)
        nearest_count: Number of levels above and below to include (default 3)
        increments: List of round number increments (in x1000 VND).
                    Loaded from config key 'round_number_increments'.
                    Default: [50, 100] meaning 50k and 100k VND
    """
    if increments is None:
        increments = DEFAULT_INCREMENTS

    seen_prices = set()
    levels = []

    for increment in sorted(increments):
        if increment <= 0:
            continue

        # Find the nearest round number below current price
        base = int(current_price / increment) * increment

        # Generate nearest_count levels below and above
        for offset in range(-nearest_count, nearest_count + 1):
            price = base + offset * increment
            if price <= 0 or price in seen_prices:
                continue
            seen_prices.add(price)

            # Label: convert back to VND for display
            vnd_price = price * 1000
            if vnd_price >= 1_000_000:
                label = f"{vnd_price / 1_000_000:.1f}M"
            else:
                label = f"{vnd_price / 1000:.0f}k"

            levels.append({
                "price": price,
                "level_type": "round",
                "description": f"Round {label}",
                "increment": increment,
            })

    return sorted(levels, key=lambda x: x["price"])


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
