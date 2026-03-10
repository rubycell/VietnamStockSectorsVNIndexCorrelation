"""Tests for price level detection."""

import pytest
import pandas as pd
from datetime import date, timedelta
from app.engine.price_levels import get_round_number_levels, detect_resistance_zones, merge_price_levels


def test_round_numbers_near_price():
    levels = get_round_number_levels(123500)
    # Should include 120k, 125k, 130k (nearest 5k and 10k)
    prices = [l["price"] for l in levels]
    assert 120000 in prices
    assert 125000 in prices
    assert 130000 in prices


def test_round_numbers_small_price():
    levels = get_round_number_levels(8500)
    prices = [l["price"] for l in levels]
    assert 5000 in prices
    assert 10000 in prices


def test_resistance_zones():
    """Swing high = price rises above SMA then dips back."""
    # Build data: stable at 100, spike to 115, drop back to 100
    closes = [100] * 12 + [105, 110, 115, 112, 105, 98, 95, 100]
    highs = [c * 1.02 for c in closes]
    lows = [c * 0.98 for c in closes]
    n = len(closes)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    df = pd.DataFrame({
        "date": dates, "open": closes, "high": highs, "low": lows, "close": closes, "volume": [1e6]*n
    })

    zones = detect_resistance_zones(df, sma_period=10)
    assert len(zones) >= 1
    # Resistance should be near the high of the spike
    assert any(z["price"] > 110 for z in zones)


def test_merge_price_levels():
    auto = [{"price": 120000, "level_type": "round", "description": "Round 120k"}]
    resistance = [{"price": 117300, "level_type": "resistance", "description": "Swing high"}]
    manual = [{"price": 115000, "level_type": "manual", "description": "User target"}]

    merged = merge_price_levels(auto, resistance, manual)
    assert len(merged) == 3
    # Sorted by price
    prices = [l["price"] for l in merged]
    assert prices == sorted(prices)
