"""Price levels API — swing lows, swing highs, round numbers, manual levels."""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Price, SwingLow, SwingHigh, PriceLevel, Config as ConfigModel
from app.engine.swing_low import detect_swing_lows, filter_active_swing_lows
from app.engine.swing_high import detect_swing_highs, filter_active_swing_highs
from app.engine.price_levels import get_round_number_levels

router = APIRouter(prefix="/api/levels", tags=["levels"])


def _parse_increments(config_value: str | None) -> list[float]:
    """Parse round_number_increments config value like '50,100'.

    Values are in x1000 VND (matching vnstock price format).
    So 50 = 50,000 VND, 100 = 100,000 VND.
    """
    if not config_value:
        return [50, 100]
    try:
        return [float(v.strip()) for v in config_value.split(",") if v.strip()]
    except ValueError:
        return [50, 100]


def _get_ohlcv_dataframe(ticker: str, session: Session) -> pd.DataFrame:
    """Load price data as DataFrame."""
    prices = (
        session.query(Price)
        .filter_by(ticker=ticker)
        .order_by(Price.date)
        .all()
    )
    if not prices:
        return pd.DataFrame()

    return pd.DataFrame([{
        "date": p.date, "open": p.open, "high": p.high,
        "low": p.low, "close": p.close, "volume": p.volume,
    } for p in prices])


@router.get("/{ticker}")
def get_ticker_levels(
    ticker: str,
    detect: bool = Query(True, description="Re-detect swing lows/highs from price data"),
    session: Session = Depends(get_database_session),
):
    """Get all price levels for a ticker: swing lows, active swing highs, round numbers, manual levels."""
    ticker = ticker.upper()

    df = _get_ohlcv_dataframe(ticker, session)
    if df.empty:
        raise HTTPException(404, f"No price data for {ticker}")

    current_price = float(df.iloc[-1]["close"])

    # --- Swing Lows (with invalidation like swing highs) ---
    if detect:
        swing_low_results = detect_swing_lows(df)
        active_swing_lows = filter_active_swing_lows(swing_low_results, df)

        # Clear old swing lows for this ticker and re-insert with active flag
        session.query(SwingLow).filter_by(ticker=ticker).delete()
        for sl in swing_low_results:
            is_active = sl in active_swing_lows
            session.add(SwingLow(
                ticker=ticker, date=sl["date"], price=sl["price"],
                confirmed=sl["confirmed"],
                point_a_date=sl.get("point_a_date"),
                point_b_date=sl.get("point_b_date"),
                active=is_active,
                invalidated_at=None if is_active else df.iloc[-1]["date"],
            ))
        session.flush()

    active_swing_lows_db = (
        session.query(SwingLow)
        .filter_by(ticker=ticker, active=True)
        .order_by(SwingLow.date.desc())
        .all()
    )

    # --- Swing Highs ---
    if detect:
        swing_high_results = detect_swing_highs(df)
        active_swing_highs = filter_active_swing_highs(swing_high_results, df)

        # Clear old swing highs for this ticker and re-insert
        session.query(SwingHigh).filter_by(ticker=ticker).delete()
        for sh in swing_high_results:
            is_active = sh in active_swing_highs
            session.add(SwingHigh(
                ticker=ticker, date=sh["date"], price=sh["price"],
                confirmed=sh["confirmed"],
                point_a_date=sh.get("point_a_date"),
                point_b_date=sh.get("point_b_date"),
                active=is_active,
                invalidated_at=None if is_active else df.iloc[-1]["date"],
            ))
        session.flush()

    active_swing_highs_db = (
        session.query(SwingHigh)
        .filter_by(ticker=ticker, active=True)
        .order_by(SwingHigh.date.desc())
        .all()
    )

    # --- Round Numbers (from config) ---
    config_entry = session.query(ConfigModel).filter_by(key="round_number_increments").first()
    increments = _parse_increments(config_entry.value if config_entry else None)
    round_levels = get_round_number_levels(current_price, increments=increments)

    # --- Manual Levels ---
    manual_levels_db = (
        session.query(PriceLevel)
        .filter_by(ticker=ticker)
        .order_by(PriceLevel.price)
        .all()
    )

    session.commit()

    # Latest active confirmed swing low
    latest_swing_low = None
    for sl in active_swing_lows_db:
        if sl.confirmed:
            latest_swing_low = {"date": str(sl.date), "price": sl.price}
            break

    return {
        "ticker": ticker,
        "current_price": current_price,
        "latest_swing_low": latest_swing_low,
        "active_swing_lows": [
            {
                "date": str(sl.date),
                "price": sl.price,
                "confirmed": sl.confirmed,
            }
            for sl in active_swing_lows_db
        ],
        "active_swing_highs": [
            {
                "date": str(sh.date),
                "price": sh.price,
                "confirmed": sh.confirmed,
            }
            for sh in active_swing_highs_db
        ],
        "round_levels": round_levels,
        "manual_levels": [
            {
                "id": ml.id,
                "price": ml.price,
                "level_type": ml.level_type,
                "description": ml.description,
            }
            for ml in manual_levels_db
        ],
    }


@router.post("/{ticker}/manual")
def add_manual_level(
    ticker: str,
    price: float = Query(...),
    description: str = Query("Manual level"),
    level_type: str = Query("support"),
    session: Session = Depends(get_database_session),
):
    """Add a manual price level for a ticker."""
    ticker = ticker.upper()
    level = PriceLevel(
        ticker=ticker, price=price,
        level_type=level_type, description=description,
    )
    session.add(level)
    session.commit()
    return {"id": level.id, "ticker": ticker, "price": price, "description": description}


@router.delete("/{ticker}/manual/{level_id}")
def delete_manual_level(
    ticker: str,
    level_id: int,
    session: Session = Depends(get_database_session),
):
    """Delete a manual price level."""
    level = session.query(PriceLevel).filter_by(id=level_id, ticker=ticker.upper()).first()
    if not level:
        raise HTTPException(404, "Level not found")
    session.delete(level)
    session.commit()
    return {"deleted": level_id}
