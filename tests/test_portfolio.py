"""Tests for portfolio engine."""

import pytest
from datetime import date
from app.database import create_engine_and_tables, get_session
from app.models import TradeFill, ImportBatch


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = get_session(engine)
    session = factory()

    # Create an import batch
    batch = ImportBatch(filename="test.xlsx", account_type="margin", row_count=0)
    session.add(batch)
    session.commit()

    yield session, batch.id
    session.close()


def _add_fill(session, batch_id, ticker, side, volume, price, value, fee=0, tax=0, return_pnl=0, trading_date=None, order_no=None):
    fill = TradeFill(
        order_no=order_no or f"ORD-{ticker}-{side}-{volume}",
        ticker=ticker,
        trading_date=trading_date or date(2025, 1, 15),
        trade_side=side,
        order_volume=volume,
        order_price=price,
        matched_volume=volume,
        matched_price=price,
        matched_value=value,
        fee=fee,
        tax=tax,
        return_pnl=return_pnl,
        account_type="margin",
        import_batch_id=batch_id,
    )
    session.add(fill)
    session.commit()
    return fill


def test_single_buy(db_session):
    session, batch_id = db_session
    _add_fill(session, batch_id, "FPT", "BUY", 100, 120000, 12000000, fee=17000)

    from app.engine.portfolio import calculate_holdings

    holdings = calculate_holdings(session)

    assert len(holdings) == 1
    h = holdings[0]
    assert h["ticker"] == "FPT"
    assert h["total_shares"] == 100
    assert h["avg_cost"] == pytest.approx((12000000 + 17000) / 100)
    assert h["realized_pnl"] == 0


def test_buy_then_sell(db_session):
    session, batch_id = db_session
    _add_fill(session, batch_id, "FPT", "BUY", 100, 120000, 12000000)
    _add_fill(session, batch_id, "FPT", "SELL", 50, 130000, 6500000, return_pnl=500000)

    from app.engine.portfolio import calculate_holdings

    holdings = calculate_holdings(session)

    h = holdings[0]
    assert h["total_shares"] == 50  # 100 - 50
    assert h["realized_pnl"] == 500000


def test_fully_sold_excluded(db_session):
    session, batch_id = db_session
    _add_fill(session, batch_id, "FPT", "BUY", 100, 120000, 12000000)
    _add_fill(session, batch_id, "FPT", "SELL", 100, 130000, 13000000, return_pnl=1000000)

    from app.engine.portfolio import calculate_holdings

    holdings = calculate_holdings(session)
    # Fully sold tickers should still appear with 0 shares for realized PnL tracking
    h = [x for x in holdings if x["ticker"] == "FPT"]
    assert h[0]["total_shares"] == 0


def test_multiple_tickers(db_session):
    session, batch_id = db_session
    _add_fill(session, batch_id, "FPT", "BUY", 100, 120000, 12000000)
    _add_fill(session, batch_id, "VCB", "BUY", 200, 90000, 18000000)

    from app.engine.portfolio import calculate_holdings

    holdings = calculate_holdings(session)
    tickers = {h["ticker"] for h in holdings}
    assert tickers == {"FPT", "VCB"}


def test_position_count_sells_from_highest_price(db_session):
    """Sells consume highest-price positions first.

    Example from user:
    - Buy 200 @ 150k (position A)
    - Buy 500 @ 200k (position B, more expensive)
    - Sell 100 → removes from B (B has 400 left) → 2 positions
    - Sell 400 → removes rest of B (B=0) → 1 position (A)
    - Sell 100 → removes from A (A has 100 left) → 1 position
    - Sell 100 → A=0 → 0 positions
    """
    from app.engine.portfolio import (
        _build_buy_positions, _apply_sells_to_positions, _count_active_positions,
    )

    session, batch_id = db_session

    # Buy 200 @ 150k
    _add_fill(session, batch_id, "FPT", "BUY", 200, 150000, 30000000,
              order_no="BUY-A", trading_date=date(2025, 1, 10))
    # Buy 500 @ 200k
    _add_fill(session, batch_id, "FPT", "BUY", 500, 200000, 100000000,
              order_no="BUY-B", trading_date=date(2025, 1, 15))

    buys = [f for f in session.query(TradeFill).filter_by(ticker="FPT").all()
            if f.trade_side == "BUY"]

    # Sell 100 → still 2 positions (B: 400 left, A: 200 left)
    positions = _build_buy_positions(buys)
    _apply_sells_to_positions(positions, 100)
    assert _count_active_positions(positions) == 2

    # Sell 500 total → 1 position (B fully consumed, A: 200 left)
    positions = _build_buy_positions(buys)
    _apply_sells_to_positions(positions, 500)
    assert _count_active_positions(positions) == 1

    # Sell 600 total → 1 position (B gone, A: 100 left)
    positions = _build_buy_positions(buys)
    _apply_sells_to_positions(positions, 600)
    assert _count_active_positions(positions) == 1

    # Sell 700 total → 0 positions (all gone)
    positions = _build_buy_positions(buys)
    _apply_sells_to_positions(positions, 700)
    assert _count_active_positions(positions) == 0


def test_position_count_via_calculate_holdings(db_session):
    """End-to-end: position_number reflects sell-from-highest logic."""
    from app.engine.portfolio import calculate_holdings

    session, batch_id = db_session

    # Buy 200 @ 150k
    _add_fill(session, batch_id, "FPT", "BUY", 200, 150000, 30000000,
              order_no="BUY-A", trading_date=date(2025, 1, 10))
    # Buy 500 @ 200k
    _add_fill(session, batch_id, "FPT", "BUY", 500, 200000, 100000000,
              order_no="BUY-B", trading_date=date(2025, 1, 15))
    # Sell 500 → B fully consumed, A still has 200
    _add_fill(session, batch_id, "FPT", "SELL", 500, 210000, 105000000,
              order_no="SELL-1", trading_date=date(2025, 2, 1))

    holdings = calculate_holdings(session)
    h = holdings[0]
    assert h["total_shares"] == 200
    assert h["position_number"] == 1  # Only position A remains


def test_avg_cost_with_multiple_buys(db_session):
    session, batch_id = db_session
    # Buy 100 @ 120k = 12M
    _add_fill(session, batch_id, "FPT", "BUY", 100, 120000, 12000000, fee=10000, order_no="BUY1", trading_date=date(2025, 1, 10))
    # Buy 200 @ 110k = 22M
    _add_fill(session, batch_id, "FPT", "BUY", 200, 110000, 22000000, fee=20000, order_no="BUY2", trading_date=date(2025, 1, 15))

    from app.engine.portfolio import calculate_holdings

    holdings = calculate_holdings(session)
    h = holdings[0]
    assert h["total_shares"] == 300
    # avg_cost = (12M + 10k + 22M + 20k) / 300 = 34030000 / 300
    expected_avg_cost = (12000000 + 10000 + 22000000 + 20000) / 300
    assert h["avg_cost"] == pytest.approx(expected_avg_cost)
    assert h["position_number"] == 2  # 2 distinct buy orders, no sells
