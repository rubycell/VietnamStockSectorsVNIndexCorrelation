"""SQLAlchemy ORM models for the portfolio trading system."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    Boolean, Text, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    account_type = Column(String, nullable=False)
    imported_at = Column(DateTime, default=datetime.utcnow)
    row_count = Column(Integer, default=0)
    date_range_start = Column(Date, nullable=True)
    date_range_end = Column(Date, nullable=True)
    fills = relationship("TradeFill", back_populates="import_batch")


class TradeFill(Base):
    __tablename__ = "trade_fills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String, nullable=False)
    ticker = Column(String, nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    trade_side = Column(String, nullable=False)
    order_volume = Column(Integer, nullable=True)
    order_price = Column(Float, nullable=True)
    matched_volume = Column(Integer, nullable=False)
    matched_price = Column(Float, nullable=False)
    matched_value = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    cost_basis = Column(Float, nullable=True)
    return_pnl = Column(Float, default=0.0)
    channel = Column(String, nullable=True)
    status = Column(String, nullable=True)
    order_type = Column(String, nullable=True)
    account_type = Column(String, nullable=False)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=False)
    import_batch = relationship("ImportBatch", back_populates="fills")
    # No unique constraint — same order can have multiple partial fills
    # with identical (order_no, price, volume, date) but different cost_basis


class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String, unique=True, nullable=False)
    ticker = Column(String, nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    trade_side = Column(String, nullable=False)
    total_matched_volume = Column(Integer, nullable=False)
    vwap_matched_price = Column(Float, nullable=False)
    total_matched_value = Column(Float, nullable=False)
    total_fee = Column(Float, default=0.0)
    total_tax = Column(Float, default=0.0)
    total_return_pnl = Column(Float, default=0.0)
    account_type = Column(String, nullable=False)
    order_type = Column(String, nullable=True)


class Holding(Base):
    __tablename__ = "holdings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, unique=True, nullable=False, index=True)
    total_shares = Column(Integer, default=0)
    avg_cost = Column("vwap_cost", Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    current_price = Column(Float, nullable=True)
    position_number = Column(Integer, default=1)
    last_updated = Column(DateTime, default=datetime.utcnow)


class Position(Base):
    """Editable position record — can be auto-generated from trades or manually created."""
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    order_no = Column(String, nullable=True)
    size = Column(Integer, nullable=False, default=0)
    avg_price = Column(Float, nullable=False, default=0.0)
    remaining = Column(Integer, nullable=False, default=0)
    sold = Column(Integer, nullable=False, default=0)
    is_manual = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    __table_args__ = (UniqueConstraint("ticker", "date", name="unique_price"),)


class SwingLow(Base):
    __tablename__ = "swing_lows"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    price = Column(Float, nullable=False)
    confirmed = Column(Boolean, default=False)
    point_a_date = Column(Date, nullable=True)
    point_b_date = Column(Date, nullable=True)
    active = Column(Boolean, default=True)
    invalidated_at = Column(Date, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)


class SwingHigh(Base):
    __tablename__ = "swing_highs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    price = Column(Float, nullable=False)
    confirmed = Column(Boolean, default=False)
    point_a_date = Column(Date, nullable=True)
    point_b_date = Column(Date, nullable=True)
    active = Column(Boolean, default=True)
    invalidated_at = Column(Date, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)


class PriceLevel(Base):
    __tablename__ = "price_levels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    level_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=True, index=True)
    rule_id = Column(String, nullable=True)
    agent_id = Column(String, nullable=True)
    severity = Column(String, default="warning")
    message = Column(Text, nullable=False)
    fud_context = Column(Text, nullable=True)
    sent_telegram = Column(Boolean, default=False)
    sent_discord = Column(Boolean, default=False)
    sent_whatsapp = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    edoc_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    source = Column(String, nullable=True)
    date = Column(String, nullable=True)
    detail_url = Column(String, nullable=True)
    download_url = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    report_source = Column(String, default="vietstock")
    ticker = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notebook(Base):
    """Maps tickers and report categories to persistent NotebookLM notebooks."""
    __tablename__ = "notebooks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_type = Column(String, nullable=False, index=True)  # "ticker" or "category"
    notebook_key = Column(String, nullable=False, index=True)   # e.g. "HPG" or "bao_cao_vi_mo"
    notebook_id = Column(String, nullable=False)                # NotebookLM remote ID
    display_name = Column(String, nullable=False)               # Human-readable name
    source_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("notebook_type", "notebook_key", name="unique_notebook_mapping"),
    )


class Config(Base):
    __tablename__ = "config"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    agent_type = Column(String, nullable=False)
    prompt_template = Column(Text, nullable=True)
    schedule = Column(String, default="on_demand")
    enabled = Column(Boolean, default=True)
    alert_on_result = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    runs = relationship("AgentRun", back_populates="agent")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")
    generated_code = Column(Text, nullable=True)
    input_context = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    agent = relationship("Agent", back_populates="runs")
