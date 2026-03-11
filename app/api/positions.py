"""Positions API — CRUD for editable position records."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Position

router = APIRouter(prefix="/api/positions", tags=["positions"])


class PositionCreate(BaseModel):
    ticker: str
    order_no: str | None = None
    size: int
    avg_price: float
    remaining: int
    sold: int = 0


class PositionUpdate(BaseModel):
    size: int | None = None
    avg_price: float | None = None
    remaining: int | None = None
    sold: int | None = None


def _position_to_dict(position: Position) -> dict:
    return {
        "id": position.id,
        "ticker": position.ticker,
        "order_no": position.order_no,
        "size": position.size,
        "avg_price": position.avg_price,
        "remaining": position.remaining,
        "sold": position.sold,
        "is_manual": position.is_manual,
        "status": "active" if position.remaining > 0 else "closed",
    }


@router.get("/{ticker}")
def list_positions(ticker: str, session: Session = Depends(get_database_session)):
    """List all positions for a ticker."""
    positions = (
        session.query(Position)
        .filter_by(ticker=ticker.upper())
        .order_by(Position.avg_price)
        .all()
    )
    return [_position_to_dict(p) for p in positions]


@router.post("/{ticker}")
def create_position(
    ticker: str,
    body: PositionCreate,
    session: Session = Depends(get_database_session),
):
    """Create a new manual position."""
    position = Position(
        ticker=ticker.upper(),
        order_no=body.order_no,
        size=body.size,
        avg_price=body.avg_price,
        remaining=body.remaining,
        sold=body.sold,
        is_manual=True,
    )
    session.add(position)
    session.commit()
    session.refresh(position)
    return _position_to_dict(position)


@router.put("/{position_id}")
def update_position(
    position_id: int,
    body: PositionUpdate,
    session: Session = Depends(get_database_session),
):
    """Update an existing position's editable fields."""
    position = session.query(Position).filter_by(id=position_id).first()
    if not position:
        raise HTTPException(404, f"Position {position_id} not found")

    if body.size is not None:
        position.size = body.size
    if body.avg_price is not None:
        position.avg_price = body.avg_price
    if body.remaining is not None:
        position.remaining = body.remaining
    if body.sold is not None:
        position.sold = body.sold

    position.updated_at = datetime.utcnow()
    session.commit()
    return _position_to_dict(position)


@router.delete("/{position_id}")
def delete_position(
    position_id: int,
    session: Session = Depends(get_database_session),
):
    """Delete a position."""
    position = session.query(Position).filter_by(id=position_id).first()
    if not position:
        raise HTTPException(404, f"Position {position_id} not found")

    session.delete(position)
    session.commit()
    return {"deleted": True, "id": position_id}


@router.post("/{ticker}/sync")
def sync_positions_from_trades(
    ticker: str,
    session: Session = Depends(get_database_session),
):
    """Sync positions from trade fills. Creates Position records from computed positions.

    Only syncs if no positions exist yet for this ticker. Does not overwrite manual edits.
    """
    ticker = ticker.upper()
    existing = session.query(Position).filter_by(ticker=ticker).count()
    if existing > 0:
        return {"synced": False, "message": "Positions already exist. Delete them first to re-sync."}

    from app.models import TradeFill
    from app.engine.portfolio import _build_buy_positions, _apply_sells_to_positions

    fills = session.query(TradeFill).filter_by(ticker=ticker).order_by(TradeFill.trading_date).all()
    buys = [f for f in fills if f.trade_side == "BUY"]
    sells = [f for f in fills if f.trade_side == "SELL"]
    total_sold = sum(f.matched_volume for f in sells)

    positions = _build_buy_positions(buys)
    _apply_sells_to_positions(positions, total_sold)

    created = []
    for p in positions:
        sold_shares = p["total_shares"] - p["remaining_shares"]
        position = Position(
            ticker=ticker,
            order_no=p["order_no"],
            size=p["total_shares"],
            avg_price=round(p["avg_price"], 2),
            remaining=p["remaining_shares"],
            sold=sold_shares,
            is_manual=False,
        )
        session.add(position)
        created.append(position)

    session.commit()
    return {"synced": True, "count": len(created)}
