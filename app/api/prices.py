"""Price data API — cache and fetch from vnstock."""

import time
from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.main import get_database_session
from app.models import Price
from app.config import VNSTOCK_SOURCE

router = APIRouter(prefix="/api/prices", tags=["prices"])


class FetchRequest(BaseModel):
    tickers: list[str]
    days_back: int = 365


def _fetch_from_vnstock(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV data from vnstock. Separated for easy mocking."""
    from vnstock import Quote
    quote = Quote(symbol=ticker, source=VNSTOCK_SOURCE)
    return quote.history(start=start, end=end, interval="1D")


@router.get("/{ticker}")
def get_prices(ticker: str, session: Session = Depends(get_database_session)):
    """Get cached prices for a ticker."""
    prices = (
        session.query(Price)
        .filter_by(ticker=ticker.upper())
        .order_by(Price.date)
        .all()
    )

    return {
        "ticker": ticker.upper(),
        "count": len(prices),
        "prices": [
            {
                "date": str(price.date),
                "open": price.open,
                "high": price.high,
                "low": price.low,
                "close": price.close,
                "volume": price.volume,
            }
            for price in prices
        ],
    }


@router.post("/fetch")
def fetch_prices(body: FetchRequest, session: Session = Depends(get_database_session)):
    """Fetch latest prices from vnstock and cache them."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=body.days_back)).strftime("%Y-%m-%d")

    results = {}
    errors = {}

    for ticker in body.tickers:
        ticker = ticker.upper()

        # Find latest cached date to only fetch new data
        latest = (
            session.query(Price.date)
            .filter_by(ticker=ticker)
            .order_by(Price.date.desc())
            .first()
        )
        if latest:
            fetch_start = (latest[0] + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            fetch_start = start_date

        try:
            dataframe = _fetch_from_vnstock(ticker, fetch_start, end_date)

            if dataframe is None or len(dataframe) == 0:
                results[ticker] = 0
                continue

            count = 0
            for _, row in dataframe.iterrows():
                price_date = row.get("time") or row.get("date")
                if isinstance(price_date, pd.Timestamp):
                    price_date = price_date.date()
                elif isinstance(price_date, str):
                    price_date = datetime.strptime(price_date, "%Y-%m-%d").date()

                price = Price(
                    ticker=ticker,
                    date=price_date,
                    open=float(row.get("open", 0)),
                    high=float(row.get("high", 0)),
                    low=float(row.get("low", 0)),
                    close=float(row.get("close", 0)),
                    volume=float(row.get("volume", 0)),
                )
                try:
                    session.add(price)
                    session.flush()
                    count += 1
                except IntegrityError:
                    session.rollback()

            results[ticker] = count

        except Exception as err:
            errors[ticker] = str(err)

        # Rate limit: 5s between requests
        if len(body.tickers) > 1:
            time.sleep(5)

    session.commit()

    return {"fetched": results, "errors": errors}
