"""Portfolio engine — calculate holdings from trade fills."""

from datetime import date

from sqlalchemy.orm import Session

from app.models import TradeFill, Holding


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

        # Position number = count of distinct BUY order_no values
        buy_order_numbers = sorted(set(fill.order_no for fill in buys))
        position_number = len(buy_order_numbers)

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


def get_position_number(buy_dates: list[date]) -> int:
    """Count distinct buy entries (each date = one position add)."""
    return len(buy_dates)


def update_holdings_table(session: Session, holdings_data: list[dict]) -> None:
    """Upsert holdings data into the holdings table."""
    for data in holdings_data:
        existing = session.query(Holding).filter_by(ticker=data["ticker"]).first()
        if existing:
            existing.total_shares = data["total_shares"]
            existing.vwap_cost = data["vwap_cost"]
            existing.total_cost = data["total_cost"]
            existing.realized_pnl = data["realized_pnl"]
            existing.position_number = data["position_number"]
        else:
            holding = Holding(
                ticker=data["ticker"],
                total_shares=data["total_shares"],
                vwap_cost=data["vwap_cost"],
                total_cost=data["total_cost"],
                realized_pnl=data["realized_pnl"],
                position_number=data["position_number"],
            )
            session.add(holding)
    session.commit()
