"""Trading rules engine — evaluates 9 custom trading rules.

Rules:
#1 no_prediction - Dashboard disclaimer (never alerts)
#2 fud_reduce_size - FUD detected -> reduce size
#3 no_fomo_swap - Dashboard reminder (never alerts)
#4 below_swing_low_sell - Price below swing low -> sell signal
#5 stick_to_strategy - Dashboard label (never alerts)
#6 fud_reduce_further - FUD escalating -> reduce further
#7 ptp_to_swing_low - Position #2+ in profit -> partial take-profit
#8 high_entry_sell_levels - Position #1 near important level -> partial sell
#9 stoploss_all_pos2 - Position #2+ below swing low -> stop-loss
"""

from dataclasses import dataclass
from app.engine.fud import FudResult


@dataclass
class RuleContext:
    ticker: str
    current_price: float
    vwap_cost: float
    total_shares: int
    position_number: int
    latest_swing_low: float | None
    swing_low_confirmed: bool
    important_levels: list[float]
    fud: FudResult
    previous_fud_severity: str = "none"


@dataclass
class TriggeredRule:
    rule_id: str
    rule_number: int
    ticker: str
    severity: str  # "info", "warning", "critical"
    message: str
    alert: bool  # Whether to send alert (False for dashboard-only rules)


PROXIMITY_PCT = 2.0  # Within 2% of a level

SEVERITY_ORDER = {"none": 0, "medium": 1, "high": 2}


def evaluate_rules(context: RuleContext) -> list[TriggeredRule]:
    """Evaluate all 9 trading rules against a holding context.

    Returns list of triggered rules.
    """
    triggered: list[TriggeredRule] = []

    _check_rule2_fud_reduce_size(context, triggered)
    _check_rule4_below_swing_low(context, triggered)
    _check_rule6_fud_escalation(context, triggered)
    _check_rule7_ptp_to_swing_low(context, triggered)
    _check_rule8_high_entry_sell_levels(context, triggered)
    _check_rule9_stoploss_all_pos2(context, triggered)

    return triggered


def _check_rule2_fud_reduce_size(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #2: FUD detected -> reduce planned action size."""
    if not context.fud.is_fud:
        return

    sectors = (
        ", ".join(context.fud.fud_sectors)
        if context.fud.fud_sectors
        else "market-wide"
    )
    triggered.append(
        TriggeredRule(
            rule_id="fud_reduce_size",
            rule_number=2,
            ticker=context.ticker,
            severity="warning",
            message=(
                f"{context.ticker}: FUD detected ({sectors}). "
                f"Consider reducing planned action size."
            ),
            alert=True,
        )
    )


def _check_rule4_below_swing_low(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #4: Price below confirmed swing low -> consider selling."""
    if not (
        context.latest_swing_low
        and context.swing_low_confirmed
        and context.current_price < context.latest_swing_low
    ):
        return

    triggered.append(
        TriggeredRule(
            rule_id="below_swing_low_sell",
            rule_number=4,
            ticker=context.ticker,
            severity="critical",
            message=(
                f"CRITICAL: {context.ticker} closed at {context.current_price:,.0f} "
                f"below swing low {context.latest_swing_low:,.0f}. "
                f"Rule #4: consider selling."
            ),
            alert=True,
        )
    )


def _check_rule6_fud_escalation(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #6: FUD severity escalating -> reduce further."""
    if not context.fud.is_fud:
        return

    current_severity = SEVERITY_ORDER.get(context.fud.severity, 0)
    previous_severity = SEVERITY_ORDER.get(context.previous_fud_severity, 0)

    if current_severity <= previous_severity:
        return

    triggered.append(
        TriggeredRule(
            rule_id="fud_reduce_further",
            rule_number=6,
            ticker=context.ticker,
            severity="warning",
            message=(
                f"{context.ticker}: FUD intensifying "
                f"({context.previous_fud_severity} -> {context.fud.severity}). "
                f"Consider further size reduction."
            ),
            alert=True,
        )
    )


def _check_rule7_ptp_to_swing_low(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #7: Position #2+ in profit -> partial take-profit to swing low."""
    if not (
        context.position_number >= 2
        and context.current_price > context.vwap_cost
        and context.latest_swing_low
    ):
        return

    triggered.append(
        TriggeredRule(
            rule_id="ptp_to_swing_low",
            rule_number=7,
            ticker=context.ticker,
            severity="info",
            message=(
                f"{context.ticker} position #{context.position_number}. "
                f"BE at {context.vwap_cost:,.0f}, "
                f"nearest swing low at {context.latest_swing_low:,.0f}. "
                f"Consider partial take-profit to pull BE to swing low."
            ),
            alert=True,
        )
    )


def _check_rule8_high_entry_sell_levels(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #8: Position #1 near important level -> partial sell."""
    if context.position_number != 1 or not context.important_levels:
        return

    for level in context.important_levels:
        distance_pct = abs(context.current_price - level) / level * 100
        if distance_pct <= PROXIMITY_PCT and context.current_price >= level * 0.98:
            triggered.append(
                TriggeredRule(
                    rule_id="high_entry_sell_levels",
                    rule_number=8,
                    ticker=context.ticker,
                    severity="info",
                    message=(
                        f"{context.ticker} reaching important level {level:,.0f}. "
                        f"Entry was at {context.vwap_cost:,.0f}. "
                        f"Consider partial sell."
                    ),
                    alert=True,
                )
            )
            break  # Only alert for nearest level


def _check_rule9_stoploss_all_pos2(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #9: Position #2+ below swing low -> stop-loss all."""
    if not (
        context.position_number >= 2
        and context.latest_swing_low
        and context.swing_low_confirmed
        and context.current_price < context.latest_swing_low
    ):
        return

    triggered.append(
        TriggeredRule(
            rule_id="stoploss_all_pos2",
            rule_number=9,
            ticker=context.ticker,
            severity="critical",
            message=(
                f"CRITICAL: {context.ticker} position #{context.position_number} "
                f"below swing low {context.latest_swing_low:,.0f}. "
                f"Rule #9: stop-loss all, may keep up to 200 shares."
            ),
            alert=True,
        )
    )
