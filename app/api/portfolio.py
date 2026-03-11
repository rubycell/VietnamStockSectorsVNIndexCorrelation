"""Portfolio API — holdings and P&L."""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Holding, TradeFill, Price, Position
from app.engine.portfolio import _build_buy_positions, _apply_sells_to_positions

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _normalize_price(holding):
    """Normalize current_price to raw VND.

    Some tickers store price in x1000 VND (e.g., FPT=79.5 meaning 79,500),
    others in raw VND (e.g., VCB=60400). Detect by comparing with avg_cost.
    """
    raw_price = holding.current_price or 0
    if holding.avg_cost and raw_price > 0 and holding.avg_cost > raw_price * 100:
        return raw_price * 1000
    return raw_price


def _compute_unrealized_from_positions(position_details, current_price):
    """Compute unrealized P&L from positions' actual cost basis."""
    active = [p for p in position_details if p["status"] == "active"]
    remaining = sum(p["remaining"] for p in active)
    cost = sum(p["avg_price"] * p["remaining"] for p in active)
    market_value = current_price * remaining
    return round(market_value - cost, 2) if remaining > 0 else 0, remaining


@router.get("")
def get_portfolio(session: Session = Depends(get_database_session)):
    """Get full portfolio summary — all numbers computed from trades."""
    holdings = session.query(Holding).order_by(Holding.ticker).all()

    holdings_data = []
    total_realized = 0
    total_unrealized = 0

    for h in holdings:
        current_price = _normalize_price(h)

        # Compute from trades
        fills = session.query(TradeFill).filter_by(ticker=h.ticker).order_by(TradeFill.trading_date).all()
        trade_summary = _compute_summary_from_trades(fills)

        # Get positions for unrealized P&L
        stored_positions = session.query(Position).filter_by(ticker=h.ticker).all()
        if stored_positions:
            position_details = [
                {"avg_price": p.avg_price, "remaining": p.remaining,
                 "status": "active" if p.remaining > 0 else "closed"}
                for p in stored_positions
            ]
        else:
            buys = [f for f in fills if f.trade_side == "BUY"]
            sells = [f for f in fills if f.trade_side == "SELL"]
            total_sold_vol = sum(f.matched_volume for f in sells)
            positions = _build_buy_positions(buys)
            _apply_sells_to_positions(positions, total_sold_vol)
            position_details = [
                {"avg_price": p["avg_price"], "remaining": p["remaining_shares"],
                 "status": "active" if p["remaining_shares"] > 0 else "closed"}
                for p in positions
            ]

        unrealized, active_remaining = _compute_unrealized_from_positions(position_details, current_price)
        active_count = sum(1 for p in position_details if p["status"] == "active")

        holding_dict = {
            "ticker": h.ticker,
            "total_shares": trade_summary["net_shares"],
            "avg_cost": trade_summary["avg_cost"],
            "total_cost": trade_summary["total_buy_cost"],
            "realized_pnl": trade_summary["realized_pnl"],
            "unrealized_pnl": unrealized,
            "current_price": current_price,
            "position_number": active_count,
        }
        holdings_data.append(holding_dict)
        total_realized += trade_summary["realized_pnl"]
        total_unrealized += unrealized

    return {
        "holdings": holdings_data,
        "total_cost": sum(h["total_cost"] for h in holdings_data),
        "total_realized_pnl": round(total_realized, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_holdings": len(holdings),
    }


def _compute_summary_from_trades(fills):
    """Derive trade-based numbers from trade history (single source of truth).

    Returns dict with: total_bought, total_sold, net_shares, total_buy_cost,
    total_sell_revenue, total_fees, avg_cost, realized_pnl.
    Unrealized P&L is computed separately from positions (their actual cost basis).
    """
    buys = [f for f in fills if f.trade_side == "BUY"]
    sells = [f for f in fills if f.trade_side == "SELL"]

    total_bought = sum(f.matched_volume for f in buys)
    total_sold = sum(f.matched_volume for f in sells)
    net_shares = total_bought - total_sold

    total_buy_cost = sum(f.matched_value for f in buys)
    total_buy_fees = sum(f.fee for f in buys)
    total_sell_revenue = sum(f.matched_value for f in sells)
    total_sell_fees = sum(f.fee for f in sells)
    total_fees = total_buy_fees + total_sell_fees

    # Average cost of all bought shares
    avg_cost = total_buy_cost / total_bought if total_bought > 0 else 0

    # Realized P&L: sell revenue - proportional cost of sold shares - all fees
    cost_of_sold = avg_cost * total_sold
    realized_pnl = total_sell_revenue - cost_of_sold - total_fees

    return {
        "total_bought": total_bought,
        "total_sold": total_sold,
        "net_shares": net_shares,
        "total_buy_cost": round(total_buy_cost, 2),
        "total_sell_revenue": round(total_sell_revenue, 2),
        "total_fees": round(total_fees, 2),
        "avg_cost": round(avg_cost, 2),
        "realized_pnl": round(realized_pnl, 2),
    }


@router.get("/{ticker}")
def get_holding(ticker: str, session: Session = Depends(get_database_session)):
    """Get a single ticker's holding details with position breakdown."""
    ticker = ticker.upper()
    holding = session.query(Holding).filter_by(ticker=ticker).first()
    if not holding:
        raise HTTPException(404, f"No holding for {ticker}")

    # Trade history is the single source of truth
    fills = session.query(TradeFill).filter_by(ticker=ticker).order_by(TradeFill.trading_date).all()

    current_price_raw = _normalize_price(holding)

    # Compute summary from trades
    trade_summary = _compute_summary_from_trades(fills)

    # Positions: stored or computed from trades
    stored_positions = (
        session.query(Position)
        .filter_by(ticker=ticker)
        .order_by(Position.avg_price)
        .all()
    )

    if stored_positions:
        position_details = [
            {
                "id": p.id,
                "order_no": p.order_no,
                "size": p.size,
                "avg_price": p.avg_price,
                "remaining": p.remaining,
                "sold": p.sold,
                "is_manual": p.is_manual,
                "status": "active" if p.remaining > 0 else "closed",
            }
            for p in stored_positions
        ]
    else:
        buys = [f for f in fills if f.trade_side == "BUY"]
        sells = [f for f in fills if f.trade_side == "SELL"]
        total_sold_vol = sum(f.matched_volume for f in sells)

        positions = _build_buy_positions(buys)
        _apply_sells_to_positions(positions, total_sold_vol)

        position_details = []
        for position in sorted(positions, key=lambda p: p["avg_price"]):
            position_details.append({
                "id": None,
                "order_no": position["order_no"],
                "size": position["total_shares"],
                "avg_price": position["avg_price"],
                "remaining": position["remaining_shares"],
                "sold": position["total_shares"] - position["remaining_shares"],
                "is_manual": False,
                "status": "active" if position["remaining_shares"] > 0 else "closed",
            })

    # Unrealized P&L from positions (actual cost basis per position)
    unrealized_pnl, position_remaining = _compute_unrealized_from_positions(position_details, current_price_raw)
    trade_summary["unrealized_pnl"] = unrealized_pnl

    # Reconciliation: do positions match trade-derived totals?
    reconciled = position_remaining == trade_summary["net_shares"]

    trade_history = [
        {
            "id": f.id,
            "order_no": f.order_no,
            "date": str(f.trading_date),
            "side": f.trade_side,
            "volume": f.matched_volume,
            "price": f.matched_price,
            "value": f.matched_value,
            "fee": f.fee,
            "pnl": f.return_pnl,
        }
        for f in fills
    ]

    # Fetch OHLCV for the chart (last 120 trading days)
    prices = (
        session.query(Price)
        .filter_by(ticker=ticker)
        .order_by(Price.date.desc())
        .limit(120)
        .all()
    )
    ohlcv = [
        {
            "time": str(p.date),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
        }
        for p in reversed(prices)
    ] if prices else []

    return {
        "ticker": holding.ticker,
        "current_price": current_price_raw,
        "trade_summary": trade_summary,
        "reconciled": reconciled,
        "position_remaining": position_remaining,
        "positions": position_details,
        "trades": trade_history,
        "ohlcv": ohlcv,
    }
