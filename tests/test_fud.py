"""Tests for FUD detection engine."""

import pytest
from app.engine.fud import detect_fud, FudResult


def test_no_fud_calm_market():
    vnindex_change = 0.5  # 0.5% change
    sector_oversold = {"Ngân hàng": 20.0}  # only 20% oversold
    result = detect_fud(vnindex_change, sector_oversold, volatility_threshold=2.0)
    assert result.is_fud is False
    assert len(result.reasons) == 0


def test_fud_from_volatility():
    vnindex_change = -3.5  # -3.5% drop
    sector_oversold = {}
    result = detect_fud(vnindex_change, sector_oversold, volatility_threshold=2.0)
    assert result.is_fud is True
    assert any("volatility" in r.lower() or "VN-Index" in r for r in result.reasons)


def test_fud_from_sector_oversold():
    vnindex_change = 0.3
    sector_oversold = {"Ngân hàng": 60.0, "Bất động sản": 55.0}  # >50%
    result = detect_fud(vnindex_change, sector_oversold, oversold_threshold=50.0)
    assert result.is_fud is True
    assert len(result.fud_sectors) >= 2


def test_fud_both_triggers():
    vnindex_change = -4.0
    sector_oversold = {"Ngân hàng": 70.0}
    result = detect_fud(vnindex_change, sector_oversold, volatility_threshold=2.0)
    assert result.is_fud is True
    assert result.severity == "high"


def test_fud_severity_levels():
    # Single trigger = medium
    r1 = detect_fud(-3.0, {}, volatility_threshold=2.0)
    assert r1.severity == "medium"

    # Both triggers = high
    r2 = detect_fud(-3.0, {"Banks": 60.0}, volatility_threshold=2.0)
    assert r2.severity == "high"


def test_custom_thresholds():
    result = detect_fud(-1.5, {}, volatility_threshold=1.0)
    assert result.is_fud is True  # 1.5 > 1.0 threshold
