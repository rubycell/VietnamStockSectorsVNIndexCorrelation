"""Import portfolio snapshot — parse broker table into synthetic trades.

Trades remain the single source of truth. Snapshot import replaces existing
trades + positions for each ticker with synthetic trades that produce the
exact same portfolio state as the broker shows.

Strategy: ALL buys at avg_cost. Sell price reverse-engineered from realized_pnl.
This guarantees position avg_price == broker avg_cost, and
realized_pnl computed from trades == broker realized_pnl.
"""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Position, Holding, TradeFill

router = APIRouter(prefix="/api/import-snapshot", tags=["import"])

SNAPSHOT_ACCOUNT_TYPE = "SNAPSHOT"


class SnapshotImport(BaseModel):
    text: str


def _parse_number(text: str) -> float:
    """Parse a number string, removing commas and handling +/- signs."""
    cleaned = text.strip().replace(",", "").replace("+", "")
    if not cleaned or cleaned == "-":
        return 0
    try:
        return float(cleaned)
    except ValueError:
        return 0


def _parse_markdown_table(text: str) -> list[dict]:
    """Parse a markdown table or CSV into a list of row dicts."""
    lines = text.strip().split("\n")

    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[\s|:-]+$", line):
            continue

        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c != ""]

        if not cells:
            continue

        first_cell = cells[0].lower()
        if "mã" in first_cell or "ticker" in first_cell:
            continue

        rows.append(cells)

    parsed = []
    for cells in rows:
        if len(cells) < 3:
            continue

        # Column 0: "ACB 23.20" → ticker + current_price (x1000 VND)
        ticker_cell = cells[0].strip()
        parts = ticker_cell.split()
        ticker = parts[0].upper()
        current_price = _parse_number(parts[1]) * 1000 if len(parts) > 1 else 0

        # Column 1: "1,150 Được GD 1,150 ..." → first number is total shares
        shares_text = cells[1] if len(cells) > 1 else "0"
        shares_match = re.match(r"[\s]*([0-9,]+)", shares_text.strip())
        total_shares = int(_parse_number(shares_match.group(1))) if shares_match else 0

        # Column 2: avg cost (raw VND)
        avg_cost = _parse_number(cells[2]) if len(cells) > 2 else 0

        # Column 4: realized P&L
        realized_text = cells[4] if len(cells) > 4 else "0"
        realized_match = re.match(r"[+\-]?[\d,]+", realized_text.strip())
        realized_pnl = _parse_number(realized_match.group()) if realized_match else 0

        # Column 6-9: buy/sell totals
        total_bought = int(_parse_number(cells[6])) if len(cells) > 6 else 0
        total_buy_value = _parse_number(cells[7]) if len(cells) > 7 else 0
        total_sold = int(_parse_number(cells[8])) if len(cells) > 8 else 0
        total_sell_value = _parse_number(cells[9]) if len(cells) > 9 else 0

        parsed.append({
            "ticker": ticker,
            "total_shares": total_shares,
            "avg_cost": avg_cost,
            "current_price": current_price,
            "realized_pnl": realized_pnl,
            "total_bought": total_bought,
            "total_buy_value": total_buy_value,
            "total_sold": total_sold,
            "total_sell_value": total_sell_value,
        })

    return parsed


def _create_synthetic_trades(session, ticker, row, today):
    """Create synthetic trades that produce exact broker numbers.

    All buys at avg_cost. Sell price derived from realized_pnl.
    Result: position avg = avg_cost, realized P&L = broker's number.
    """
    total_shares = row["total_shares"]
    avg_cost = row["avg_cost"]
    realized_pnl = row["realized_pnl"]
    total_sold = row["total_sold"]

    # If broker doesn't report sell volume but has realized P&L,
    # we need at least 1 share sold to carry the P&L
    if realized_pnl != 0 and total_sold == 0:
        total_sold = 1

    # Total bought = current holding + everything sold
    total_buy_volume = total_shares + total_sold
    trades_created = 0

    # BUY trade: everything at avg_cost
    if total_buy_volume > 0:
        buy_value = avg_cost * total_buy_volume
        session.add(TradeFill(
            ticker=ticker,
            order_no=f"SNAPSHOT-BUY-{today.isoformat()}",
            trading_date=today,
            trade_side="BUY",
            matched_volume=total_buy_volume,
            matched_price=avg_cost,
            matched_value=buy_value,
            fee=0,
            return_pnl=0,
            account_type=SNAPSHOT_ACCOUNT_TYPE,
            import_batch_id=0,
        ))
        trades_created += 1

    # SELL trade: price that produces the exact realized_pnl
    # realized_pnl = sell_value - avg_cost * total_sold
    # sell_value = realized_pnl + avg_cost * total_sold
    if total_sold > 0:
        sell_value = realized_pnl + avg_cost * total_sold
        sell_price = sell_value / total_sold
        session.add(TradeFill(
            ticker=ticker,
            order_no=f"SNAPSHOT-SELL-{today.isoformat()}",
            trading_date=today,
            trade_side="SELL",
            matched_volume=total_sold,
            matched_price=sell_price,
            matched_value=sell_value,
            fee=0,
            return_pnl=0,
            account_type=SNAPSHOT_ACCOUNT_TYPE,
            import_batch_id=0,
        ))
        trades_created += 1

    # Position record (for per-position tracking)
    if total_shares > 0:
        session.add(Position(
            ticker=ticker,
            order_no=f"SNAPSHOT-{today.isoformat()}",
            size=total_shares,
            avg_price=avg_cost,
            remaining=total_shares,
            sold=0,
            is_manual=True,
        ))

    return trades_created


@router.post("")
def import_snapshot(
    body: SnapshotImport,
    session: Session = Depends(get_database_session),
):
    """Full portfolio replace from broker snapshot.

    For each ticker: delete old data, create synthetic trades.
    Tickers NOT in snapshot: cleaned up (sold out).
    """
    today = date.today()
    parsed = _parse_markdown_table(body.text)
    if not parsed:
        raise HTTPException(400, "Could not parse any rows from the input")

    # Wipe ALL existing trades, positions, holdings first.
    # Snapshot is a full portfolio replace — no mixing with old data.
    session.query(TradeFill).delete()
    session.query(Position).delete()
    session.query(Holding).delete()

    results = []
    for row in parsed:
        ticker = row["ticker"]

        # Create synthetic trades
        trades_created = _create_synthetic_trades(session, ticker, row, today)

        # Update or create Holding
        current_price = row["current_price"]
        holding = session.query(Holding).filter_by(ticker=ticker).first()
        if holding:
            holding.current_price = current_price
            holding.avg_cost = row["avg_cost"]
            holding.total_shares = row["total_shares"]
            holding.total_cost = row["avg_cost"] * row["total_shares"]
            holding.realized_pnl = row["realized_pnl"]
        elif row["total_shares"] > 0:
            session.add(Holding(
                ticker=ticker,
                total_shares=row["total_shares"],
                avg_cost=row["avg_cost"],
                total_cost=row["avg_cost"] * row["total_shares"],
                realized_pnl=row["realized_pnl"],
                unrealized_pnl=0,
                current_price=current_price,
                position_number=1,
            ))

        results.append({
            "ticker": ticker,
            "shares": row["total_shares"],
            "avg_cost": row["avg_cost"],
            "current_price": current_price,
            "trades_created": trades_created,
        })

    session.commit()

    return {
        "imported": len(results),
        "tickers": results,
    }
