"""Swing low detection and retrieval API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import SwingLow, Price
from app.engine.swing_low import detect_swing_lows

router = APIRouter(prefix="/api/swing-lows", tags=["swing-lows"])


class DetectRequest(BaseModel):
    ticker: str
    sma_period: int = 10


@router.post("/detect")
def detect(body: DetectRequest, session: Session = Depends(get_database_session)):
    """Detect swing lows for a ticker using cached price data."""
    import pandas as pd

    prices = (
        session.query(Price)
        .filter_by(ticker=body.ticker.upper())
        .order_by(Price.date)
        .all()
    )

    if not prices:
        raise HTTPException(404, f"No price data for {body.ticker}")

    df = pd.DataFrame([{
        "date": p.date, "open": p.open, "high": p.high,
        "low": p.low, "close": p.close, "volume": p.volume,
    } for p in prices])

    results = detect_swing_lows(df, sma_period=body.sma_period)

    # Store results
    for sl in results:
        existing = (
            session.query(SwingLow)
            .filter_by(ticker=body.ticker.upper(), date=sl["date"])
            .first()
        )
        if not existing:
            session.add(SwingLow(
                ticker=body.ticker.upper(),
                date=sl["date"],
                price=sl["price"],
                confirmed=sl["confirmed"],
                point_a_date=sl.get("point_a_date"),
                point_b_date=sl.get("point_b_date"),
            ))

    session.commit()

    return {
        "ticker": body.ticker.upper(),
        "swing_lows": [
            {
                "date": str(sl["date"]),
                "price": sl["price"],
                "confirmed": sl["confirmed"],
                "point_a_date": str(sl.get("point_a_date")) if sl.get("point_a_date") else None,
                "point_b_date": str(sl.get("point_b_date")) if sl.get("point_b_date") else None,
            }
            for sl in results
        ],
    }


@router.get("/{ticker}")
def get_swing_lows(ticker: str, session: Session = Depends(get_database_session)):
    """Get stored swing lows for a ticker."""
    swing_lows = (
        session.query(SwingLow)
        .filter_by(ticker=ticker.upper())
        .order_by(SwingLow.date.desc())
        .all()
    )

    return {
        "ticker": ticker.upper(),
        "swing_lows": [
            {
                "date": str(sl.date),
                "price": sl.price,
                "confirmed": sl.confirmed,
                "point_a_date": str(sl.point_a_date) if sl.point_a_date else None,
                "point_b_date": str(sl.point_b_date) if sl.point_b_date else None,
            }
            for sl in swing_lows
        ],
    }
