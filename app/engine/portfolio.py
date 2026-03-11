"""Portfolio engine — calculate holdings from trade fills.

Position counting logic:
- Each distinct buy order (by order_no) is one position.
- When selling, shares are removed from the highest-price position first.
- Position count = number of buy positions that still have remaining shares.
"""

from sqlalchemy.orm import Session

from app.models import TradeFill, Holding


def _build_buy_positions(buys: list) -> list[dict]:
    """Group buy fills by order_no, aggregate shares and compute avg price.

    Returns list sorted by matched_price descending (highest first),
    so sells consume expensive positions first.
    """
    positions_by_order = {}
    for fill in buys:
        key = fill.order_no
        if key not in positions_by_order:
            positions_by_order[key] = {
                "order_no": key,
                "total_shares": 0,
                "total_value": 0.0,
                "avg_price": 0.0,
            }
        positions_by_order[key]["total_shares"] += fill.matched_volume
        positions_by_order[key]["total_value"] += fill.matched_value

    positions = list(positions_by_order.values())
    for position in positions:
        if position["total_shares"] > 0:
            position["avg_price"] = position["total_value"] / position["total_shares"]
        position["remaining_shares"] = position["total_shares"]

    # Sort highest price first — sells consume these first
    positions.sort(key=lambda p: p["avg_price"], reverse=True)
    return positions


def _apply_sells_to_positions(positions: list[dict], total_sold: int) -> list[dict]:
    """Remove sold shares from positions, highest price first.

    Returns the same list with updated remaining_shares.
    """
    shares_to_sell = total_sold
    for position in positions:
        if shares_to_sell <= 0:
            break
        consumed = min(position["remaining_shares"], shares_to_sell)
        position["remaining_shares"] -= consumed
        shares_to_sell -= consumed
    return positions


def _count_active_positions(positions: list[dict]) -> int:
    """Count positions that still have remaining shares."""
    return sum(1 for p in positions if p["remaining_shares"] > 0)


def calculate_holdings(session: Session) -> list[dict]:
    """Calculate current holdings from all trade fills.

    Returns list of dicts with: ticker, total_shares, vwap_cost, total_cost,
    realized_pnl, position_number.
    """
    tickers = [
        row[0] for row in
        session.query(TradeFill.ticker).distinct().all()
    ]

    results = []
    for ticker in sorted(tickers):
        fills = session.query(TradeFill).filter_by(ticker=ticker).all()

        buys = [fill for fill in fills if fill.trade_side == "BUY"]
        sells = [fill for fill in fills if fill.trade_side == "SELL"]

        total_bought = sum(fill.matched_volume for fill in buys)
        total_sold = sum(fill.matched_volume for fill in sells)
        total_shares = total_bought - total_sold

        # VWAP cost = (sum of buy values + fees) / total bought
        if total_bought > 0:
            total_buy_cost = sum(fill.matched_value + fill.fee for fill in buys)
            vwap_cost = total_buy_cost / total_bought
        else:
            vwap_cost = 0.0

        realized_pnl = sum(fill.return_pnl for fill in sells)

        # Position count: sell from highest-price positions first
        buy_positions = _build_buy_positions(buys)
        _apply_sells_to_positions(buy_positions, total_sold)
        position_number = _count_active_positions(buy_positions)

        results.append({
            "ticker": ticker,
            "total_shares": total_shares,
            "vwap_cost": vwap_cost,
            "total_cost": vwap_cost * total_shares if total_shares > 0 else 0.0,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": 0.0,  # Needs current_price to calculate
            "current_price": None,
            "position_number": position_number,
        })

    return results


def _fetch_live_price(ticker: str) -> float | None:
    """Fetch the latest closing price from vnstock. Returns None on failure."""
    try:
        from vnstock import Quote
        from app.config import VNSTOCK_SOURCE
        from datetime import date, timedelta

        quote = Quote(symbol=ticker, source=VNSTOCK_SOURCE)
        end = date.today() + timedelta(days=1)
        start = date.today() - timedelta(days=7)
        dataframe = quote.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1D",
        )
        if dataframe is not None and len(dataframe) > 0:
            raw_close = float(dataframe.iloc[-1]["close"])
            # vnstock VCI source returns prices in thousands of VND (e.g. 23.15 = 23,150 VND)
            # Convert to full VND to match matched_value/vwap_cost units
            return raw_close * 1000
    except (Exception, SystemExit):
        pass
    return None


def update_holdings_table(session: Session, holdings_data: list[dict]) -> None:
    """Upsert holdings data into the holdings table with current prices.

    Fetches live prices from vnstock for each ticker with shares > 0.
    Falls back to the cached prices table if vnstock fails.
    """
    import time
    from app.models import Price

    for data in holdings_data:
        current_price = None

        if data["total_shares"] > 0:
            # Try live price from vnstock first
            current_price = _fetch_live_price(data["ticker"])
            time.sleep(5)  # Rate limit: vnstock allows 20 req/min

        # Fall back to cached prices table
        if current_price is None:
            latest_price = (
                session.query(Price)
                .filter_by(ticker=data["ticker"])
                .order_by(Price.date.desc())
                .first()
            )
            current_price = latest_price.close if latest_price else None

        # Calculate unrealized P&L: (current_price - vwap_cost) * total_shares
        if current_price and data["total_shares"] > 0:
            unrealized_pnl = (current_price - data["vwap_cost"]) * data["total_shares"]
        else:
            unrealized_pnl = 0.0

        existing = session.query(Holding).filter_by(ticker=data["ticker"]).first()
        if existing:
            existing.total_shares = data["total_shares"]
            existing.vwap_cost = data["vwap_cost"]
            existing.total_cost = data["total_cost"]
            existing.realized_pnl = data["realized_pnl"]
            existing.position_number = data["position_number"]
            existing.current_price = current_price
            existing.unrealized_pnl = unrealized_pnl
        else:
            holding = Holding(
                ticker=data["ticker"],
                total_shares=data["total_shares"],
                vwap_cost=data["vwap_cost"],
                total_cost=data["total_cost"],
                realized_pnl=data["realized_pnl"],
                position_number=data["position_number"],
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
            )
            session.add(holding)
    session.commit()
