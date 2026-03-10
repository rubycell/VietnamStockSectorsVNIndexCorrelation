"""Portfolio API — holdings and P&L."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Holding

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
def get_portfolio(session: Session = Depends(get_database_session)):
    """Get full portfolio summary."""
    holdings = session.query(Holding).order_by(Holding.ticker).all()

    holdings_data = []
    total_cost = 0
    total_realized = 0
    total_unrealized = 0

    for h in holdings:
        holding_dict = {
            "ticker": h.ticker,
            "total_shares": h.total_shares,
            "vwap_cost": h.vwap_cost,
            "total_cost": h.total_cost,
            "realized_pnl": h.realized_pnl,
            "unrealized_pnl": h.unrealized_pnl,
            "current_price": h.current_price,
            "position_number": h.position_number,
        }
        holdings_data.append(holding_dict)
        total_cost += h.total_cost or 0
        total_realized += h.realized_pnl or 0
        total_unrealized += h.unrealized_pnl or 0

    return {
        "holdings": holdings_data,
        "total_cost": total_cost,
        "total_realized_pnl": total_realized,
        "total_unrealized_pnl": total_unrealized,
        "total_holdings": len(holdings),
    }


@router.get("/{ticker}")
def get_holding(ticker: str, session: Session = Depends(get_database_session)):
    """Get a single ticker's holding details."""
    holding = session.query(Holding).filter_by(ticker=ticker.upper()).first()
    if not holding:
        raise HTTPException(404, f"No holding for {ticker}")

    return {
        "ticker": holding.ticker,
        "total_shares": holding.total_shares,
        "vwap_cost": holding.vwap_cost,
        "total_cost": holding.total_cost,
        "realized_pnl": holding.realized_pnl,
        "unrealized_pnl": holding.unrealized_pnl,
        "current_price": holding.current_price,
        "position_number": holding.position_number,
    }
