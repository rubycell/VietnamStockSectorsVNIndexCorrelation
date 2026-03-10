"""FUD detection engine.

FUD (Fear, Uncertainty, Doubt) is detected via:
1. VN-Index volatility exceeding configurable threshold
2. Sector oversold percentage exceeding threshold (>50% of stocks in condition)
"""

from dataclasses import dataclass, field


@dataclass
class FudResult:
    is_fud: bool
    severity: str = "none"  # none, medium, high
    reasons: list[str] = field(default_factory=list)
    fud_sectors: list[str] = field(default_factory=list)
    vnindex_change: float = 0.0
    volatility_triggered: bool = False
    sector_triggered: bool = False


def detect_fud(
    vnindex_change: float,
    sector_oversold: dict[str, float],
    volatility_threshold: float = 2.0,
    oversold_threshold: float = 50.0,
) -> FudResult:
    """Detect FUD conditions.

    Args:
        vnindex_change: VN-Index daily change in percent (e.g., -3.5 means -3.5%)
        sector_oversold: Dict mapping sector name to % of stocks meeting oversold condition
        volatility_threshold: Absolute % change to trigger FUD (default 2.0)
        oversold_threshold: Sector % threshold (default 50.0)

    Returns:
        FudResult with detection details
    """
    reasons = []
    fud_sectors = []
    volatility_triggered = False
    sector_triggered = False

    # Check volatility
    if abs(vnindex_change) >= volatility_threshold:
        volatility_triggered = True
        direction = "dropped" if vnindex_change < 0 else "surged"
        reasons.append(
            f"VN-Index {direction} {abs(vnindex_change):.1f}%"
            f" (threshold: {volatility_threshold}%)"
        )

    # Check sector oversold
    for sector_name, percent_oversold in sector_oversold.items():
        if percent_oversold >= oversold_threshold:
            sector_triggered = True
            fud_sectors.append(sector_name)
            reasons.append(
                f"{sector_name}: {percent_oversold:.0f}% oversold"
                f" (threshold: {oversold_threshold}%)"
            )

    is_fud = volatility_triggered or sector_triggered

    if volatility_triggered and sector_triggered:
        severity = "high"
    elif is_fud:
        severity = "medium"
    else:
        severity = "none"

    return FudResult(
        is_fud=is_fud,
        severity=severity,
        reasons=reasons,
        fud_sectors=fud_sectors,
        vnindex_change=vnindex_change,
        volatility_triggered=volatility_triggered,
        sector_triggered=sector_triggered,
    )
