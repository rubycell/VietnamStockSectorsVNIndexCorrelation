"""Rules evaluation API."""

from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Holding, SwingLow, PriceLevel, Alert, Config as ConfigModel
from app.engine.rules import evaluate_rules, RuleContext
from app.engine.fud import detect_fud
from app.engine.price_levels import get_round_number_levels

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.post("/evaluate")
def evaluate(session: Session = Depends(get_database_session)):
    """Evaluate all trading rules against current holdings."""
    holdings = session.query(Holding).filter(Holding.total_shares > 0).all()

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

    all_triggered = []
    today = date.today()

    for holding in holdings:
        # Get latest confirmed swing low
        swing_low = (
            session.query(SwingLow)
            .filter_by(ticker=holding.ticker, confirmed=True)
            .order_by(SwingLow.date.desc())
            .first()
        )

        # Get manual price levels
        manual_levels = (
            session.query(PriceLevel)
            .filter_by(ticker=holding.ticker)
            .all()
        )

        current_price = holding.current_price or 0
        round_levels = (
            get_round_number_levels(current_price) if current_price > 0 else []
        )
        important_levels = (
            [level.price for level in manual_levels]
            + [level["price"] for level in round_levels]
        )

        context = RuleContext(
            ticker=holding.ticker,
            current_price=current_price,
            vwap_cost=holding.vwap_cost or 0,
            total_shares=holding.total_shares,
            position_number=holding.position_number or 1,
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
        "holdings_checked": len(holdings),
        "fud_status": {"is_fud": fud.is_fud, "severity": fud.severity},
    }
