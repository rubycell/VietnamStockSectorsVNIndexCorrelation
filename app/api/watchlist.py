"""Watchlist API — tickers to track but not necessarily held."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Holding, WatchlistItem

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    ticker: str
    notes: str = ""


@router.get("")
def list_watchlist(session: Session = Depends(get_database_session)):
    """Return all watchlist items."""
    items = session.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
    return [
        {
            "id": item.id,
            "ticker": item.ticker,
            "notes": item.notes,
            "added_at": item.added_at.isoformat() if item.added_at else None,
        }
        for item in items
    ]


@router.post("")
def add_to_watchlist(
    body: WatchlistAddRequest,
    session: Session = Depends(get_database_session),
):
    """Add a ticker to the watchlist. Idempotent — updates notes if already exists."""
    ticker = body.ticker.strip().upper()
    if not ticker:
        return {"error": "ticker is required"}

    existing = session.query(WatchlistItem).filter_by(ticker=ticker).first()
    if existing:
        existing.notes = body.notes
        session.commit()
        return {"message": f"{ticker} already on watchlist — notes updated", "ticker": ticker}

    session.add(WatchlistItem(ticker=ticker, notes=body.notes))
    session.commit()
    return {"message": f"{ticker} added to watchlist", "ticker": ticker}


@router.delete("/{ticker}")
def remove_from_watchlist(
    ticker: str,
    session: Session = Depends(get_database_session),
):
    """Remove a ticker from the watchlist."""
    ticker = ticker.strip().upper()
    item = session.query(WatchlistItem).filter_by(ticker=ticker).first()
    if not item:
        return {"error": f"{ticker} not found in watchlist"}
    session.delete(item)
    session.commit()
    return {"message": f"{ticker} removed from watchlist"}


@router.get("/notebook-tickers")
def get_notebook_tickers(session: Session = Depends(get_database_session)):
    """Return the combined set of tickers eligible for NotebookLM notebooks.

    This is the gate for notebook creation in the bulk import pipeline:
    holdings with shares > 0 UNION watchlist tickers.
    """
    portfolio_tickers = {
        h.ticker
        for h in session.query(Holding).filter(Holding.total_shares > 0).all()
    }
    watchlist_tickers = {
        w.ticker for w in session.query(WatchlistItem).all()
    }
    notebook_tickers = sorted(portfolio_tickers | watchlist_tickers)
    return {
        "notebook_tickers": notebook_tickers,
        "portfolio_count": len(portfolio_tickers),
        "watchlist_count": len(watchlist_tickers),
        "total": len(notebook_tickers),
    }
