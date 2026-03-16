"""Trading rules engine — evaluates 10 custom trading rules.

Rules:
#1 no_prediction - Dashboard disclaimer (never alerts)
#2 fud_reduce_size - FUD detected -> reduce size
#3 no_fomo_swap - Dashboard reminder (never alerts)
#4 below_swing_low_sell - Price below swing low -> sell signal
#5 stick_to_strategy - Dashboard label (never alerts)
#6 fud_reduce_further - FUD escalating -> reduce further
#7 ptp_to_swing_low - Position #2+ in profit -> partial take-profit
#8 high_entry_sell_levels - Position #1 entry far above swing low -> sell 50% to pull avg cost to swing low
#9 stoploss_all_pos2 - Position #2+ below swing low -> stop-loss
#10 underwater_below_swing - At a loss AND price below newest swing low (which is below entry) -> critical
"""

from dataclasses import dataclass
from app.engine.fud import FudResult


@dataclass
class RuleContext:
    ticker: str
    current_price: float
    avg_cost: float
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
    """Evaluate all 10 trading rules against a holding context.

    Returns list of triggered rules.
    """
    triggered: list[TriggeredRule] = []

    _check_rule2_fud_reduce_size(context, triggered)
    _check_rule4_below_swing_low(context, triggered)
    _check_rule6_fud_escalation(context, triggered)
    _check_rule7_ptp_to_swing_low(context, triggered)
    _check_rule8_high_entry_sell_levels(context, triggered)
    _check_rule9_stoploss_all_pos2(context, triggered)
    _check_rule10_underwater_below_swing(context, triggered)

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
        and context.current_price > context.avg_cost
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
                f"Avg cost {context.avg_cost:,.0f}, "
                f"nearest swing low at {context.latest_swing_low:,.0f}. "
                f"Consider partial take-profit to pull avg cost to swing low."
            ),
            alert=True,
        )
    )


def _check_rule8_high_entry_sell_levels(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #8: Position #1 entry too far above swing low -> partial sell target.

    If entry is far above the nearest swing low, calculate the price at which
    selling 50% would pull the remaining BE down to the swing low.

    Math: sell 50% at P → remaining BE = 2*entry - P
    Want BE ≤ swing_low → P ≥ 2*entry - swing_low
    Target sell level = 2 * entry - swing_low
    """
    if context.position_number != 1:
        return
    if not context.latest_swing_low or context.latest_swing_low <= 0:
        return
    if context.avg_cost <= 0:
        return

    # Only applies when entry is above the swing low
    if context.avg_cost <= context.latest_swing_low:
        return

    target_sell_level = 2 * context.avg_cost - context.latest_swing_low

    # Only alert if target is above current price (not yet reached)
    # and price is approaching it (within PROXIMITY_PCT)
    if target_sell_level <= context.current_price:
        # Already at or above target — sell now
        triggered.append(
            TriggeredRule(
                rule_id="high_entry_sell_levels",
                rule_number=8,
                ticker=context.ticker,
                severity="warning",
                message=(
                    f"{context.ticker} at {context.current_price:,.0f} is AT/ABOVE "
                    f"partial sell target {target_sell_level:,.0f}. "
                    f"Entry {context.avg_cost:,.0f}, swing low {context.latest_swing_low:,.0f}. "
                    f"Sell 50% to pull avg cost to swing low."
                ),
                alert=True,
            )
        )
        return

    distance_pct = (target_sell_level - context.current_price) / target_sell_level * 100
    if distance_pct <= PROXIMITY_PCT:
        triggered.append(
            TriggeredRule(
                rule_id="high_entry_sell_levels",
                rule_number=8,
                ticker=context.ticker,
                severity="info",
                message=(
                    f"{context.ticker} at {context.current_price:,.0f} approaching "
                    f"partial sell target {target_sell_level:,.0f} "
                    f"({distance_pct:.1f}% away). "
                    f"Entry {context.avg_cost:,.0f}, swing low {context.latest_swing_low:,.0f}. "
                    f"Sell 50% at target to pull avg cost to swing low."
                ),
                alert=True,
            )
        )


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


def _check_rule10_underwater_below_swing(
    context: RuleContext, triggered: list[TriggeredRule]
) -> None:
    """Rule #10: Position #1 at a loss, price below confirmed swing low that is below entry.

    Conditions (all must be true):
    1. Position #1
    2. At a loss: current_price < avg_cost
    3. Swing low is confirmed
    4. Swing low is below entry price (avg_cost)
    5. Current price is below that swing low
    """
    if context.position_number != 1:
        return
    if not (
        context.latest_swing_low
        and context.swing_low_confirmed
        and context.current_price < context.avg_cost
        and context.latest_swing_low < context.avg_cost
        and context.current_price < context.latest_swing_low
    ):
        return

    loss_pct = (context.avg_cost - context.current_price) / context.avg_cost * 100
    triggered.append(
        TriggeredRule(
            rule_id="underwater_below_swing",
            rule_number=10,
            ticker=context.ticker,
            severity="critical",
            message=(
                f"CRITICAL: {context.ticker} underwater at {context.current_price:,.0f} "
                f"(entry {context.avg_cost:,.0f}, loss {loss_pct:.1f}%), "
                f"broke below swing low {context.latest_swing_low:,.0f}. "
                f"Rule #10: structure broken while at a loss — review position immediately."
            ),
            alert=True,
        )
    )
