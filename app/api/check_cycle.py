"""Full check cycle endpoint — called by OpenClaw cron."""

import time
from datetime import datetime, date as date_type, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Agent, Holding, Price
from app.engine.portfolio import calculate_holdings, update_holdings_table
from app.engine.swing_low import detect_swing_lows
from app.engine.rules import evaluate_rules, RuleContext
from app.engine.fud import detect_fud
from app.engine.price_levels import get_round_number_levels, detect_resistance_zones, merge_price_levels
from app.models import SwingLow, Alert

router = APIRouter(tags=["check-cycle"])


def _fetch_prices_for_tickers(tickers: list, session: Session) -> dict:
    """Fetch latest prices from vnstock for all tickers."""
    from app.api.prices import _fetch_from_vnstock
    import pandas as pd

    fetched = {}
    errors = {}

    for ticker in tickers:
        try:
            last_price = (
                session.query(Price)
                .filter_by(ticker=ticker)
                .order_by(Price.date.desc())
                .first()
            )
            start_date = str(last_price.date) if last_price else "2025-01-01"

            end_date = str(date_type.today() + timedelta(days=1))
            new_prices = _fetch_from_vnstock(ticker, start_date, end_date)
            if new_prices is not None and not new_prices.empty:
                count = 0
                for _, row in new_prices.iterrows():
                    existing = (
                        session.query(Price)
                        .filter_by(ticker=ticker, date=row["time"])
                        .first()
                    )
                    if not existing:
                        session.add(Price(
                            ticker=ticker,
                            date=row["time"],
                            open=float(row.get("open", 0)),
                            high=float(row.get("high", 0)),
                            low=float(row.get("low", 0)),
                            close=float(row.get("close", 0)),
                            volume=int(row.get("volume", 0)),
                        ))
                        count += 1
                session.flush()
                fetched[ticker] = count
            else:
                fetched[ticker] = 0

            time.sleep(5)  # Rate limit
        except Exception as error:
            errors[ticker] = str(error)

    return {"fetched": fetched, "errors": errors}


def _detect_all_swing_lows(tickers: list, session: Session) -> dict:
    """Detect swing lows for all tickers with price data."""
    import pandas as pd

    results = {}
    for ticker in tickers:
        prices = (
            session.query(Price)
            .filter_by(ticker=ticker)
            .order_by(Price.date.asc())
            .all()
        )
        if len(prices) < 20:
            continue

        ohlcv = pd.DataFrame([
            {"date": str(p.date), "open": p.open, "high": p.high,
             "low": p.low, "close": p.close, "volume": p.volume}
            for p in prices
        ])
        swing_lows = detect_swing_lows(ohlcv)

        # Store latest swing lows
        for swing_low in swing_lows[-5:]:
            swing_date = swing_low["date"]
            if isinstance(swing_date, str):
                swing_date = datetime.strptime(swing_date, "%Y-%m-%d").date()
            existing = (
                session.query(SwingLow)
                .filter_by(ticker=ticker, date=swing_date)
                .first()
            )
            if not existing:
                session.add(SwingLow(
                    ticker=ticker,
                    date=swing_date,
                    price=float(swing_low["price"]),
                    confirmed=swing_low.get("confirmed", False),
                ))
        session.flush()
        results[ticker] = len(swing_lows)

    return results


def _evaluate_all_rules(tickers: list, session: Session) -> dict:
    """Evaluate rules for all holdings."""
    import pandas as pd

    all_triggered = []

    for ticker in tickers:
        holding = session.query(Holding).filter_by(ticker=ticker).first()
        if not holding or holding.total_shares <= 0:
            continue

        prices = (
            session.query(Price)
            .filter_by(ticker=ticker)
            .order_by(Price.date.desc())
            .limit(60)
            .all()
        )
        if not prices:
            continue

        current_price = prices[0].close
        swing_lows = (
            session.query(SwingLow)
            .filter_by(ticker=ticker, confirmed=True)
            .order_by(SwingLow.date.desc())
            .limit(5)
            .all()
        )

        ohlcv = pd.DataFrame([
            {"date": str(p.date), "open": p.open, "high": p.high,
             "low": p.low, "close": p.close, "volume": p.volume}
            for p in reversed(prices)
        ])

        round_levels = get_round_number_levels(current_price)
        resistance_levels = detect_resistance_zones(ohlcv)
        important_levels = merge_price_levels(round_levels, resistance_levels, [])

        fud_result = detect_fud(vnindex_change=0.0, sector_oversold={})

        latest_confirmed = next(
            (s for s in swing_lows if s.confirmed), None
        )

        context = RuleContext(
            ticker=ticker,
            current_price=current_price,
            avg_cost=holding.avg_cost,
            total_shares=holding.total_shares,
            position_number=holding.position_number or 1,
            latest_swing_low=latest_confirmed.price if latest_confirmed else None,
            swing_low_confirmed=latest_confirmed is not None,
            important_levels=[level["price"] for level in important_levels],
            fud=fud_result,
        )

        triggered = evaluate_rules(context)
        for rule in triggered:
            all_triggered.append({
                "rule_id": rule.rule_id,
                "rule_number": rule.rule_id.split("_")[1] if "_" in rule.rule_id else rule.rule_id,
                "ticker": ticker,
                "severity": rule.severity,
                "message": rule.message,
                "alert": rule.alert,
            })

            # Create alert (dedup: max 1 per rule+ticker per day)
            if rule.alert:
                today_start = datetime.combine(date_type.today(), datetime.min.time())
                existing_alert = (
                    session.query(Alert)
                    .filter_by(ticker=ticker, rule_id=rule.rule_id)
                    .filter(Alert.created_at >= today_start)
                    .first()
                )
                if not existing_alert:
                    session.add(Alert(
                        ticker=ticker,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=rule.message,
                    ))

    session.flush()
    return {"triggered": all_triggered, "holdings_checked": len(tickers)}


@router.post("/api/check-cycle")
def run_check_cycle(session: Session = Depends(get_database_session)):
    """Run the full hourly check: prices -> portfolio -> swing lows -> rules.

    This directly calls the engine functions instead of going through agents,
    so it works without an Anthropic API key.
    """
    tickers = [
        h.ticker
        for h in session.query(Holding.ticker).filter(Holding.total_shares > 0).all()
    ]

    results = {}
    errors = []

    # Step 1: Fetch latest prices
    try:
        price_result = _fetch_prices_for_tickers(tickers, session)
        results["price-fetch"] = price_result
    except Exception as error:
        errors.append({"step": "price-fetch", "error": str(error)})

    # Step 2: Recalculate portfolio
    try:
        holdings_data = calculate_holdings(session)
        update_holdings_table(session, holdings_data)
        results["portfolio-update"] = {"holdings_updated": len(holdings_data)}
    except Exception as error:
        errors.append({"step": "portfolio-update", "error": str(error)})

    # Step 3: Detect swing lows
    try:
        swing_result = _detect_all_swing_lows(tickers, session)
        results["swing-low-detect"] = swing_result
    except Exception as error:
        session.rollback()
        errors.append({"step": "swing-low-detect", "error": str(error)})

    # Step 4: Evaluate rules
    try:
        rules_result = _evaluate_all_rules(tickers, session)
        results["rules-evaluate"] = rules_result
    except Exception as error:
        session.rollback()
        errors.append({"step": "rules-evaluate", "error": str(error)})

    try:
        session.commit()
    except Exception:
        session.rollback()

    return {"success": len(errors) == 0, "results": results, "errors": errors}
