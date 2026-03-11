"""Trades API — CRUD for trade fill records."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import TradeFill

router = APIRouter(prefix="/api/trades", tags=["trades"])


class TradeCreate(BaseModel):
    ticker: str
    order_no: str = ""
    trading_date: date
    trade_side: str  # BUY or SELL
    matched_volume: int
    matched_price: float
    fee: float = 0.0
    return_pnl: float = 0.0


class TradeUpdate(BaseModel):
    order_no: str | None = None
    trading_date: date | None = None
    trade_side: str | None = None
    matched_volume: int | None = None
    matched_price: float | None = None
    fee: float | None = None
    return_pnl: float | None = None


def _trade_to_dict(fill: TradeFill) -> dict:
    return {
        "id": fill.id,
        "order_no": fill.order_no,
        "ticker": fill.ticker,
        "date": str(fill.trading_date),
        "side": fill.trade_side,
        "volume": fill.matched_volume,
        "price": fill.matched_price,
        "value": fill.matched_value,
        "fee": fill.fee,
        "pnl": fill.return_pnl,
    }


@router.put("/{trade_id}")
def update_trade(
    trade_id: int,
    body: TradeUpdate,
    session: Session = Depends(get_database_session),
):
    """Update an existing trade fill."""
    fill = session.query(TradeFill).filter_by(id=trade_id).first()
    if not fill:
        raise HTTPException(404, f"Trade {trade_id} not found")

    if body.order_no is not None:
        fill.order_no = body.order_no
    if body.trading_date is not None:
        fill.trading_date = body.trading_date
    if body.trade_side is not None:
        fill.trade_side = body.trade_side
    if body.matched_volume is not None:
        fill.matched_volume = body.matched_volume
    if body.matched_price is not None:
        fill.matched_price = body.matched_price
    if body.fee is not None:
        fill.fee = body.fee
    if body.return_pnl is not None:
        fill.return_pnl = body.return_pnl

    # Recompute matched_value
    fill.matched_value = fill.matched_volume * fill.matched_price

    session.commit()
    return _trade_to_dict(fill)


@router.post("/{ticker}")
def create_trade(
    ticker: str,
    body: TradeCreate,
    session: Session = Depends(get_database_session),
):
    """Create a new manual trade fill."""
    fill = TradeFill(
        ticker=ticker.upper(),
        order_no=body.order_no or f"MANUAL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        trading_date=body.trading_date,
        trade_side=body.trade_side.upper(),
        matched_volume=body.matched_volume,
        matched_price=body.matched_price,
        matched_value=body.matched_volume * body.matched_price,
        fee=body.fee,
        return_pnl=body.return_pnl,
        account_type="MANUAL",
        import_batch_id=0,
    )
    session.add(fill)
    session.commit()
    session.refresh(fill)
    return _trade_to_dict(fill)


@router.delete("/{trade_id}")
def delete_trade(
    trade_id: int,
    session: Session = Depends(get_database_session),
):
    """Delete a trade fill."""
    fill = session.query(TradeFill).filter_by(id=trade_id).first()
    if not fill:
        raise HTTPException(404, f"Trade {trade_id} not found")

    session.delete(fill)
    session.commit()
    return {"deleted": True, "id": trade_id}
