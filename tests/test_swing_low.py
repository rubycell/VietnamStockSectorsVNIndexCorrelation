"""Tests for swing low detection algorithm."""

import pytest
import pandas as pd
from datetime import date, timedelta
from app.engine.swing_low import detect_swing_lows


def _make_ohlcv(closes, lows=None):
    """Create a simple OHLCV DataFrame from close prices.

    If lows not provided, use closes as lows (simplified).
    """
    if lows is None:
        lows = closes
    n = len(closes)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": lows,
        "close": closes,
        "volume": [1000000] * n,
    })


def test_no_data_returns_empty():
    df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    result = detect_swing_lows(df)
    assert len(result) == 0


def test_not_enough_data():
    """Need at least SMA period + 1 bars."""
    df = _make_ohlcv([100] * 5)
    result = detect_swing_lows(df, sma_period=10)
    assert len(result) == 0


def test_simple_swing_low():
    """Price drops below SMA then recovers — should find one swing low."""
    # Build 20 bars: first 12 at 100 (SMA stable), then dip to 90, then back to 105
    closes = [100] * 12 + [95, 90, 88, 92, 100, 105, 108, 110]
    lows = [100] * 12 + [93, 88, 85, 90, 98, 103, 106, 108]
    df = _make_ohlcv(closes, lows)

    result = detect_swing_lows(df, sma_period=10)
    assert len(result) >= 1
    # The swing low should be the minimum low in the dip
    assert result[0]["price"] == 85  # min low during the dip


def test_swing_low_confirmed():
    """Swing low should be confirmed when Point B is found."""
    closes = [100] * 12 + [95, 90, 88, 92, 100, 105, 108, 110]
    lows = [100] * 12 + [93, 88, 85, 90, 98, 103, 106, 108]
    df = _make_ohlcv(closes, lows)

    result = detect_swing_lows(df, sma_period=10)
    assert result[0]["confirmed"] is True


def test_unconfirmed_swing_low():
    """If price dips below SMA but doesn't recover, swing low is unconfirmed."""
    closes = [100] * 12 + [95, 90, 88, 85, 83]
    lows = [100] * 12 + [93, 88, 85, 83, 80]
    df = _make_ohlcv(closes, lows)

    result = detect_swing_lows(df, sma_period=10)
    # Should have an unconfirmed swing low (still in dip)
    unconfirmed = [r for r in result if not r["confirmed"]]
    assert len(unconfirmed) >= 1


def test_multiple_swing_lows():
    """Two separate dips should produce two swing lows."""
    # First dip and recovery
    closes = [100] * 12 + [95, 90, 88, 92, 100, 105, 108, 110]
    lows = [100] * 12 + [93, 88, 85, 90, 98, 103, 106, 108]
    # Second dip and recovery
    closes += [105, 98, 92, 88, 95, 103, 108, 112]
    lows += [103, 96, 90, 86, 93, 101, 106, 110]
    df = _make_ohlcv(closes, lows)

    result = detect_swing_lows(df, sma_period=10)
    confirmed = [r for r in result if r["confirmed"]]
    assert len(confirmed) >= 2
