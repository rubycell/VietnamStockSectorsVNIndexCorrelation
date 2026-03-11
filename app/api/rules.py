"""Rules evaluation API."""

from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Holding, TradeFill, Position, SwingLow, PriceLevel, Alert, Config as ConfigModel
from app.api.portfolio import _normalize_price, _compute_summary_from_trades
from app.engine.rules import evaluate_rules, RuleContext
from app.engine.fud import detect_fud
from app.engine.price_levels import get_round_number_levels, DEFAULT_INCREMENTS

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.post("/evaluate")
def evaluate(session: Session = Depends(get_database_session)):
    """Evaluate all trading rules against current holdings.

    All numbers computed from trades + positions (single source of truth),
    NOT from the stale Holding table.
    """
    holdings = session.query(Holding).all()

    # Get FUD config
    fud_threshold_row = (
        session.query(ConfigModel)
        .filter_by(key="fud_volatility_threshold")
        .first()
    )
    fud_threshold = float(fud_threshold_row.value) if fud_threshold_row else 2.0

    previous_fud_row = (
        session.query(ConfigModel)
        .filter_by(key="previous_fud_severity")
        .first()
    )
    previous_fud_severity = previous_fud_row.value if previous_fud_row else "none"

    # Simple FUD check (no live VN-Index data yet, use 0 change)
    fud = detect_fud(0.0, {}, volatility_threshold=fud_threshold)

    # Read round number increments from config
    increment_row = (
        session.query(ConfigModel)
        .filter_by(key="round_number_increments")
        .first()
    )
    if increment_row and increment_row.value:
        try:
            round_increments = [
                float(v.strip()) for v in increment_row.value.split(",") if v.strip()
            ]
        except ValueError:
            round_increments = DEFAULT_INCREMENTS
    else:
        round_increments = DEFAULT_INCREMENTS

    all_triggered = []
    today = date.today()

    for holding in holdings:
        # Compute from trades (single source of truth)
        fills = (
            session.query(TradeFill)
            .filter_by(ticker=holding.ticker)
            .order_by(TradeFill.trading_date)
            .all()
        )
        trade_summary = _compute_summary_from_trades(fills)
        net_shares = trade_summary["net_shares"]

        # Skip tickers with no active position
        if net_shares <= 0:
            continue

        # Get positions for position count
        stored_positions = session.query(Position).filter_by(ticker=holding.ticker).all()
        active_positions = [p for p in stored_positions if p.remaining > 0]
        position_count = len(active_positions) if active_positions else 1

        # Compute avg cost from active positions
        if active_positions:
            total_remaining = sum(p.remaining for p in active_positions)
            avg_cost = (
                sum(p.avg_price * p.remaining for p in active_positions) / total_remaining
                if total_remaining > 0 else 0
            )
        else:
            avg_cost = trade_summary["avg_cost"]

        current_price = _normalize_price(holding)

        # Get latest ACTIVE confirmed swing low (not invalidated)
        swing_low = (
            session.query(SwingLow)
            .filter_by(ticker=holding.ticker, confirmed=True, active=True)
            .order_by(SwingLow.date.desc())
            .first()
        )

        # Get manual price levels
        manual_levels = (
            session.query(PriceLevel)
            .filter_by(ticker=holding.ticker)
            .all()
        )

        # Normalize to x1000 VND for consistent comparisons
        current_price_x1000 = current_price / 1000
        avg_cost_x1000 = avg_cost / 1000

        round_levels = (
            get_round_number_levels(current_price_x1000, increments=round_increments)
            if current_price_x1000 > 0 else []
        )
        important_levels = (
            [level.price for level in manual_levels]
            + [level["price"] for level in round_levels]
        )

        context = RuleContext(
            ticker=holding.ticker,
            current_price=current_price_x1000,
            avg_cost=avg_cost_x1000,
            total_shares=net_shares,
            position_number=position_count,
            latest_swing_low=swing_low.price if swing_low else None,
            swing_low_confirmed=swing_low.confirmed if swing_low else False,
            important_levels=important_levels,
            fud=fud,
            previous_fud_severity=previous_fud_severity,
        )

        triggered = evaluate_rules(context)

        # Create alerts with dedup (max 1 per rule+ticker per day)
        for rule in triggered:
            if not rule.alert:
                continue

            existing = (
                session.query(Alert)
                .filter_by(ticker=rule.ticker, rule_id=rule.rule_id)
                .filter(
                    Alert.created_at
                    >= datetime(today.year, today.month, today.day)
                )
                .first()
            )

            if not existing:
                alert = Alert(
                    ticker=rule.ticker,
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    message=rule.message,
                    fud_context=str(fud) if fud.is_fud else None,
                )
                session.add(alert)

        all_triggered.extend([
            {
                "rule_id": triggered_rule.rule_id,
                "rule_number": triggered_rule.rule_number,
                "ticker": triggered_rule.ticker,
                "severity": triggered_rule.severity,
                "message": triggered_rule.message,
                "alert": triggered_rule.alert,
            }
            for triggered_rule in triggered
        ])

    # Save FUD severity for next check
    fud_config = (
        session.query(ConfigModel)
        .filter_by(key="previous_fud_severity")
        .first()
    )
    if fud_config:
        fud_config.value = fud.severity
    else:
        session.add(
            ConfigModel(key="previous_fud_severity", value=fud.severity)
        )

    session.commit()

    return {
        "triggered": all_triggered,
        "holdings_checked": len([h for h in holdings if _has_active_position(session, h)]),
        "fud_status": {"is_fud": fud.is_fud, "severity": fud.severity},
    }


def _has_active_position(session, holding):
    """Check if a holding has active shares from trades."""
    fills = session.query(TradeFill).filter_by(ticker=holding.ticker).all()
    summary = _compute_summary_from_trades(fills)
    return summary["net_shares"] > 0
