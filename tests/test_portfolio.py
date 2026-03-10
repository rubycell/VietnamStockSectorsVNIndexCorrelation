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
    assert h["vwap_cost"] == pytest.approx((12000000 + 17000) / 100)
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


def test_position_number():
    """Position #1 = first buy, #2 = second buy, etc."""
    from app.engine.portfolio import get_position_number

    buy_dates = [date(2025, 1, 10), date(2025, 1, 15), date(2025, 2, 1)]
    assert get_position_number(buy_dates) == 3


def test_vwap_with_multiple_buys(db_session):
    session, batch_id = db_session
    # Buy 100 @ 120k = 12M
    _add_fill(session, batch_id, "FPT", "BUY", 100, 120000, 12000000, fee=10000, order_no="BUY1", trading_date=date(2025, 1, 10))
    # Buy 200 @ 110k = 22M
    _add_fill(session, batch_id, "FPT", "BUY", 200, 110000, 22000000, fee=20000, order_no="BUY2", trading_date=date(2025, 1, 15))

    from app.engine.portfolio import calculate_holdings

    holdings = calculate_holdings(session)
    h = holdings[0]
    assert h["total_shares"] == 300
    # VWAP = (12M + 10k + 22M + 20k) / 300 = 34030000 / 300
    expected_vwap = (12000000 + 10000 + 22000000 + 20000) / 300
    assert h["vwap_cost"] == pytest.approx(expected_vwap)
    assert h["position_number"] == 2  # 2 distinct buy orders
