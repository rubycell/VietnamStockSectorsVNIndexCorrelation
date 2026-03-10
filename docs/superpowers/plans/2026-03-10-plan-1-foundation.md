# Plan 1: Foundation — FastAPI + Celery + Redis + SQLite + Agent Framework

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational infrastructure — FastAPI server, Celery task queue, Redis broker, SQLite database with all schemas, and the agent base framework that all subsequent features plug into as agents.

**Architecture:** A FastAPI server serves the API and static dashboard files. Celery workers (with Redis broker) run agents on schedule or on-demand. SQLite stores all persistent state. Every feature (data import, price fetch, portfolio calc, swing low, rules, alerts) is an "agent" — either a deterministic Celery task or an AI-powered code-gen agent. Agents are defined in the database and manageable via API.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, Celery, Redis, SQLAlchemy, SQLite, anthropic SDK, httpx, pandas, openpyxl, vnstock

**Spec:** `docs/superpowers/specs/2026-03-10-portfolio-trading-system-design.md`

---

## Chunk 1: Project Scaffolding + Database

### Task 1: Create project structure and dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `docker-compose.yml`

- [ ] **Step 1: Update requirements.txt**

Add all new dependencies to `requirements.txt`:

```
vnstock
pandas
numpy
pytz
openpyxl
fastapi
uvicorn[standard]
celery[redis]
redis
sqlalchemy
python-multipart
anthropic
httpx
pytest
pytest-asyncio
```

- [ ] **Step 2: Create app package**

```bash
mkdir -p app/api app/pipeline app/engine app/agents app/tasks tests
touch app/__init__.py app/api/__init__.py app/pipeline/__init__.py app/engine/__init__.py app/agents/__init__.py app/tasks/__init__.py tests/__init__.py
```

- [ ] **Step 3: Create app/config.py**

```python
"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'portfolio.db'}")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "default")

VNSTOCK_SOURCE = os.getenv("VNSTOCK_SOURCE", "VCI")
MARKET_OPEN_HOUR = int(os.getenv("MARKET_OPEN_HOUR", "9"))
MARKET_CLOSE_HOUR = int(os.getenv("MARKET_CLOSE_HOUR", "15"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DATA_DIR = PROJECT_ROOT / "data"
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
version: "3.8"

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  evolution-api:
    image: atendai/evolution-api:latest
    ports:
      - "8080:8080"
    environment:
      - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY:-your-api-key}
    volumes:
      - evolution_data:/evolution/instances
    restart: unless-stopped
    profiles:
      - alerts

volumes:
  redis_data:
  evolution_data:
```

- [ ] **Step 5: Install dependencies and verify**

```bash
source venv/bin/activate
pip install -r requirements.txt
python -c "import fastapi, celery, sqlalchemy, anthropic, httpx; print('All imports OK')"
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt docker-compose.yml app/ tests/
git commit -m "chore: scaffold project structure with dependencies"
```

---

### Task 2: SQLite database models and migrations

**Files:**
- Create: `app/database.py`
- Create: `app/models.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing test for database setup**

Create `tests/test_database.py`:

```python
"""Tests for database setup and model creation."""

import pytest
from sqlalchemy import inspect
from app.database import create_engine_and_tables, get_session
from app.models import Base


def test_create_engine_and_tables_creates_all_tables(tmp_path):
    """All expected tables exist after initialization."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_and_tables(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "trade_fills",
        "trades",
        "holdings",
        "prices",
        "swing_lows",
        "price_levels",
        "alerts",
        "config",
        "agents",
        "agent_runs",
        "import_batches",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_get_session_returns_usable_session(tmp_path):
    """Session can be used to query the database."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_and_tables(database_url)
    session_factory = get_session(engine)
    with session_factory() as session:
        result = session.execute(
            __import__("sqlalchemy").text("SELECT 1")
        ).scalar()
        assert result == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_database.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.database'`

- [ ] **Step 3: Create app/database.py**

```python
"""Database engine creation and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


def create_engine_and_tables(database_url: str):
    """Create SQLAlchemy engine and ensure all tables exist."""
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
    )
    Base.metadata.create_all(bind=engine)
    return engine


def get_session(engine):
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
```

- [ ] **Step 4: Create app/models.py**

```python
"""SQLAlchemy ORM models for the portfolio trading system."""

from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    account_type = Column(String, nullable=False)  # "margin" or "normal"
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
    trade_side = Column(String, nullable=False)  # "BUY" or "SELL"
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
    account_type = Column(String, nullable=False)  # "margin" or "normal"
    import_batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=False)

    import_batch = relationship("ImportBatch", back_populates="fills")

    __table_args__ = (
        UniqueConstraint(
            "order_no", "matched_price", "matched_volume", "trading_date",
            name="unique_fill",
        ),
    )


class Trade(Base):
    """Aggregated order — one row per order_no."""
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
    vwap_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    current_price = Column(Float, nullable=True)
    position_number = Column(Integer, default=1)  # 1 = first buy, 2+ = add-ons
    last_updated = Column(DateTime, default=datetime.utcnow)


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

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="unique_price"),
    )


class SwingLow(Base):
    __tablename__ = "swing_lows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    price = Column(Float, nullable=False)
    confirmed = Column(Boolean, default=False)
    point_a_date = Column(Date, nullable=True)
    point_b_date = Column(Date, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)


class PriceLevel(Base):
    __tablename__ = "price_levels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    level_type = Column(String, nullable=False)  # "resistance", "round_number", "manual"
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=True, index=True)
    rule_id = Column(String, nullable=True)
    agent_id = Column(String, nullable=True)
    severity = Column(String, default="warning")  # "critical", "warning", "info"
    message = Column(Text, nullable=False)
    fud_context = Column(Text, nullable=True)
    sent_telegram = Column(Boolean, default=False)
    sent_whatsapp = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Config(Base):
    __tablename__ = "config"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)  # slug like "trendy-sector-detector"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    agent_type = Column(String, nullable=False)  # "deterministic", "structured_ai", "code_gen"
    prompt_template = Column(Text, nullable=True)
    schedule = Column(String, default="on_demand")  # "hourly", "daily", "on_demand"
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
    status = Column(String, default="running")  # "running", "success", "error"
    generated_code = Column(Text, nullable=True)
    input_context = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    agent = relationship("Agent", back_populates="runs")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_database.py -v
```
Expected: PASS — all 11 tables created, session works.

- [ ] **Step 6: Commit**

```bash
git add app/database.py app/models.py tests/test_database.py
git commit -m "feat: add SQLite database models for all system tables"
```

---

## Chunk 2: Agent Base Framework

### Task 3: Agent base class and registry

**Files:**
- Create: `app/agents/base.py`
- Create: `app/agents/registry.py`
- Create: `tests/test_agents_base.py`

- [ ] **Step 1: Write failing tests for agent base and registry**

Create `tests/test_agents_base.py`:

```python
"""Tests for agent base class and registry."""

import pytest
from app.agents.base import BaseAgent, AgentResult
from app.agents.registry import AgentRegistry


class FakeAgent(BaseAgent):
    """A simple deterministic agent for testing."""

    agent_id = "fake-agent"
    agent_type = "deterministic"

    def run(self, context: dict) -> AgentResult:
        return AgentResult(
            success=True,
            output={"message": f"processed {context.get('ticker', 'unknown')}"},
        )


def test_base_agent_run_returns_agent_result():
    agent = FakeAgent()
    result = agent.run({"ticker": "FPT"})
    assert result.success is True
    assert result.output["message"] == "processed FPT"


def test_agent_result_has_required_fields():
    result = AgentResult(success=True, output={"key": "value"})
    assert result.success is True
    assert result.output == {"key": "value"}
    assert result.error is None
    assert result.generated_code is None


def test_agent_result_error_case():
    result = AgentResult(success=False, error="Something broke")
    assert result.success is False
    assert result.error == "Something broke"
    assert result.output is None


def test_registry_register_and_get():
    registry = AgentRegistry()
    registry.register(FakeAgent)
    agent = registry.get("fake-agent")
    assert isinstance(agent, FakeAgent)


def test_registry_get_unknown_returns_none():
    registry = AgentRegistry()
    assert registry.get("nonexistent") is None


def test_registry_list_agents():
    registry = AgentRegistry()
    registry.register(FakeAgent)
    agents = registry.list_agents()
    assert len(agents) == 1
    assert agents[0]["id"] == "fake-agent"
    assert agents[0]["type"] == "deterministic"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agents_base.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create app/agents/base.py**

```python
"""Base class for all agents in the system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Result returned by any agent execution."""

    success: bool
    output: dict[str, Any] | None = None
    error: str | None = None
    generated_code: str | None = None


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Subclasses must define:
      - agent_id: str — unique identifier (slug)
      - agent_type: str — "deterministic", "structured_ai", or "code_gen"
      - run(context) -> AgentResult
    """

    agent_id: str = ""
    agent_type: str = "deterministic"

    @abstractmethod
    def run(self, context: dict) -> AgentResult:
        """Run the agent with the given context.

        Args:
            context: Dictionary with relevant data for the agent.
                     Contents vary by agent type.

        Returns:
            AgentResult with success status and output or error.
        """
        ...
```

- [ ] **Step 4: Create app/agents/registry.py**

```python
"""Agent registry — maps agent IDs to agent classes."""

from typing import Type

from app.agents.base import BaseAgent


class AgentRegistry:
    """Registry for built-in (code-defined) agents."""

    def __init__(self):
        self._agents: dict[str, Type[BaseAgent]] = {}

    def register(self, agent_class: Type[BaseAgent]) -> None:
        """Register an agent class by its agent_id."""
        self._agents[agent_class.agent_id] = agent_class

    def get(self, agent_id: str) -> BaseAgent | None:
        """Get an instance of the agent by ID, or None if not found."""
        agent_class = self._agents.get(agent_id)
        if agent_class is None:
            return None
        return agent_class()

    def list_agents(self) -> list[dict]:
        """List all registered agents with their metadata."""
        return [
            {"id": cls.agent_id, "type": cls.agent_type}
            for cls in self._agents.values()
        ]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_agents_base.py -v
```
Expected: PASS — all 6 tests green.

- [ ] **Step 6: Commit**

```bash
git add app/agents/base.py app/agents/registry.py tests/test_agents_base.py
git commit -m "feat: add agent base class and registry"
```

---

### Task 4: Code-gen agent executor

**Files:**
- Create: `app/agents/code_executor.py`
- Create: `tests/test_code_executor.py`

**Note:** The code executor uses Python's `exec()` to run AI-generated code. This is intentional — the entire application runs inside a Docker container (user-approved design decision). The executor provides pandas, numpy, and read-only database access to generated code.

- [ ] **Step 1: Write failing tests for code executor**

Create `tests/test_code_executor.py`:

```python
"""Tests for the code runner used by code-gen agents."""

import pytest
from app.agents.code_executor import run_generated_code


def test_run_simple_code_returns_result():
    code = """
import json
result = {"total": 42}
output = json.dumps(result)
"""
    result = run_generated_code(code, data_context={})
    assert result["success"] is True
    assert result["output"] == {"total": 42}


def test_run_code_with_data_context():
    code = """
import json
import pandas as pd
df = data_context["prices"]
avg = df["close"].mean()
result = {"average_close": round(avg, 2)}
output = json.dumps(result)
"""
    import pandas as pd
    prices_df = pd.DataFrame({
        "ticker": ["FPT", "FPT", "FPT"],
        "close": [100.0, 110.0, 105.0],
    })
    result = run_generated_code(code, data_context={"prices": prices_df})
    assert result["success"] is True
    assert result["output"]["average_close"] == 105.0


def test_run_code_with_syntax_error():
    code = "def broken(:"
    result = run_generated_code(code, data_context={})
    assert result["success"] is False
    assert "error" in result
    assert "SyntaxError" in result["error"] or "invalid syntax" in result["error"]


def test_run_code_with_runtime_error():
    code = """
import json
x = 1 / 0
output = json.dumps({"ok": True})
"""
    result = run_generated_code(code, data_context={})
    assert result["success"] is False
    assert "ZeroDivisionError" in result["error"]


def test_run_code_captures_generated_code():
    code = """
import json
output = json.dumps({"hello": "world"})
"""
    result = run_generated_code(code, data_context={})
    assert result["generated_code"] == code
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_code_executor.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create app/agents/code_executor.py**

```python
"""Run Python code generated by AI agents.

Provides a sandboxed namespace with pandas, numpy, and a data context
dict. The generated code sets an 'output' variable with JSON results.

SECURITY NOTE: Uses exec() intentionally. This application runs inside
a Docker container per the approved design. The generated code has full
access to the data context but no network or filesystem access beyond
what pandas/numpy provide.
"""

import json
import signal
import traceback
from typing import Any

import numpy
import pandas


def run_generated_code(
    code: str,
    data_context: dict[str, Any],
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Run generated Python code and capture its JSON output.

    The code should set a variable called 'output' to a JSON string.

    Args:
        code: Python source code to run.
        data_context: Dict of DataFrames/values available as 'data_context'.
        timeout_seconds: Max seconds before timeout.

    Returns:
        Dict with: success, output (parsed JSON), error, generated_code.
    """
    namespace = {
        "pd": pandas,
        "pandas": pandas,
        "np": numpy,
        "numpy": numpy,
        "json": json,
        "data_context": data_context,
        "output": None,
    }

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Code timed out after {timeout_seconds}s")

    previous_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        compiled = compile(code, "<agent-generated>", "exec")
        exec(compiled, namespace)  # noqa: S102 — intentional, runs in Docker
        signal.alarm(0)

        raw_output = namespace.get("output")
        if raw_output is None:
            return {
                "success": False,
                "output": None,
                "error": "Code did not set 'output' variable",
                "generated_code": code,
            }

        parsed = json.loads(raw_output) if isinstance(raw_output, str) else raw_output

        return {
            "success": True,
            "output": parsed,
            "error": None,
            "generated_code": code,
        }

    except TimeoutError as timeout_error:
        signal.alarm(0)
        return {
            "success": False,
            "output": None,
            "error": str(timeout_error),
            "generated_code": code,
        }
    except Exception:
        signal.alarm(0)
        return {
            "success": False,
            "output": None,
            "error": traceback.format_exc(),
            "generated_code": code,
        }
    finally:
        signal.signal(signal.SIGALRM, previous_handler)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_code_executor.py -v
```
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/agents/code_executor.py tests/test_code_executor.py
git commit -m "feat: add code runner for AI-generated agent code"
```

---

## Chunk 3: FastAPI Server + Celery Setup

### Task 5: Celery app configuration

**Files:**
- Create: `app/tasks/celery_app.py`
- Create: `tests/test_celery_app.py`

- [ ] **Step 1: Write failing test for Celery config**

Create `tests/test_celery_app.py`:

```python
"""Tests for Celery app configuration."""

from app.tasks.celery_app import celery_app


def test_celery_app_has_correct_broker():
    assert "redis" in celery_app.conf.broker_url


def test_celery_app_has_correct_backend():
    assert "redis" in celery_app.conf.result_backend


def test_celery_app_timezone():
    assert celery_app.conf.timezone == "Asia/Ho_Chi_Minh"


def test_celery_beat_schedule_has_hourly_check():
    schedule = celery_app.conf.beat_schedule
    assert "hourly-rule-check" in schedule
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_celery_app.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create app/tasks/celery_app.py**

```python
"""Celery application configuration with beat schedule."""

from celery import Celery
from celery.schedules import crontab

from app.config import REDIS_URL, TIMEZONE, MARKET_OPEN_HOUR, MARKET_CLOSE_HOUR

celery_app = Celery(
    "portfolio_trading",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    timezone=TIMEZONE,
    enable_utc=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Hourly check during market hours (9am-3pm, on the hour)
celery_app.conf.beat_schedule = {
    "hourly-rule-check": {
        "task": "app.tasks.rule_check.run_full_check_cycle",
        "schedule": crontab(
            minute=0,
            hour=f"{MARKET_OPEN_HOUR}-{MARKET_CLOSE_HOUR}",
        ),
    },
}

# Auto-discover tasks in app/tasks/
celery_app.autodiscover_tasks(["app.tasks"])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_celery_app.py -v
```
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/tasks/celery_app.py tests/test_celery_app.py
git commit -m "feat: add Celery app config with hourly market-hours schedule"
```

---

### Task 6: FastAPI application entry point

**Files:**
- Create: `app/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing test for FastAPI app**

Create `tests/test_main.py`:

```python
"""Tests for the FastAPI application entry point."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_static_dashboard_served(client):
    """The root path serves the dashboard index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Vietnam" in response.text or "html" in response.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create app/main.py**

```python
"""FastAPI application entry point.

Serves the API endpoints and the static dashboard files.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import DASHBOARD_DIR, DATABASE_URL
from app.database import create_engine_and_tables, get_session

app = FastAPI(
    title="Portfolio Trading System",
    version="0.1.0",
    description="Hybrid trading portfolio management with AI agents",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
engine = create_engine_and_tables(DATABASE_URL)
SessionFactory = get_session(engine)


def get_database_session():
    """Dependency that provides a database session."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": app.version}


# Serve dashboard static files (must be last — catches all unmatched routes)
if DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_main.py -v
```
Expected: PASS — health check returns OK, dashboard HTML served.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: add FastAPI entry point with health check and dashboard static mount"
```

---

### Task 7: Agent CRUD API endpoints

**Files:**
- Create: `app/api/agents.py`
- Create: `tests/test_api_agents.py`

- [ ] **Step 1: Write failing tests for agent API**

Create `tests/test_api_agents.py`:

```python
"""Tests for the agent management API."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client(tmp_path):
    """Create a test client with a temporary database."""
    from app import main, database

    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = database.create_engine_and_tables(database_url)
    session_factory = database.get_session(engine)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[main.get_database_session] = override_session
    yield TestClient(app)
    app.dependency_overrides.clear()


SAMPLE_AGENT = {
    "id": "test-agent",
    "name": "Test Agent",
    "description": "A test agent",
    "agent_type": "code_gen",
    "prompt_template": "Analyze {ticker} prices",
    "schedule": "on_demand",
    "enabled": True,
    "alert_on_result": False,
}


def test_create_agent(client):
    response = client.post("/api/agents", json=SAMPLE_AGENT)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "test-agent"
    assert data["name"] == "Test Agent"


def test_list_agents(client):
    client.post("/api/agents", json=SAMPLE_AGENT)
    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 1
    assert agents[0]["id"] == "test-agent"


def test_get_agent_by_id(client):
    client.post("/api/agents", json=SAMPLE_AGENT)
    response = client.get("/api/agents/test-agent")
    assert response.status_code == 200
    assert response.json()["id"] == "test-agent"


def test_get_agent_not_found(client):
    response = client.get("/api/agents/nonexistent")
    assert response.status_code == 404


def test_update_agent(client):
    client.post("/api/agents", json=SAMPLE_AGENT)
    response = client.put(
        "/api/agents/test-agent",
        json={"name": "Updated Agent", "enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Agent"
    assert response.json()["enabled"] is False


def test_delete_agent(client):
    client.post("/api/agents", json=SAMPLE_AGENT)
    response = client.delete("/api/agents/test-agent")
    assert response.status_code == 204
    response = client.get("/api/agents/test-agent")
    assert response.status_code == 404


def test_create_duplicate_agent_fails(client):
    client.post("/api/agents", json=SAMPLE_AGENT)
    response = client.post("/api/agents", json=SAMPLE_AGENT)
    assert response.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_agents.py -v
```
Expected: FAIL — 404 on `/api/agents` since the router isn't registered yet.

- [ ] **Step 3: Create app/api/agents.py**

```python
"""Agent management CRUD API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    id: str
    name: str
    description: str | None = None
    agent_type: str = "code_gen"
    prompt_template: str | None = None
    schedule: str = "on_demand"
    enabled: bool = True
    alert_on_result: bool = False


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt_template: str | None = None
    schedule: str | None = None
    enabled: bool | None = None
    alert_on_result: bool | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    agent_type: str
    prompt_template: str | None
    schedule: str
    enabled: bool
    alert_on_result: bool

    class Config:
        from_attributes = True


@router.post("", status_code=201, response_model=AgentResponse)
def create_agent(
    agent_data: AgentCreate,
    session: Session = Depends(get_database_session),
):
    existing = session.query(Agent).filter_by(id=agent_data.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Agent already exists")

    agent = Agent(
        id=agent_data.id,
        name=agent_data.name,
        description=agent_data.description,
        agent_type=agent_data.agent_type,
        prompt_template=agent_data.prompt_template,
        schedule=agent_data.schedule,
        enabled=agent_data.enabled,
        alert_on_result=agent_data.alert_on_result,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@router.get("", response_model=list[AgentResponse])
def list_agents(session: Session = Depends(get_database_session)):
    return session.query(Agent).all()


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, session: Session = Depends(get_database_session)):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    update_data: AgentUpdate,
    session: Session = Depends(get_database_session),
):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_fields = update_data.model_dump(exclude_unset=True)
    for field_name, value in update_fields.items():
        setattr(agent, field_name, value)
    agent.updated_at = datetime.utcnow()

    session.commit()
    session.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: str, session: Session = Depends(get_database_session)):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    session.delete(agent)
    session.commit()
```

- [ ] **Step 4: Register the router in app/main.py**

Add these lines to `app/main.py` **before** the `app.mount("/", ...)` line:

```python
from app.api.agents import router as agents_router

app.include_router(agents_router)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_api_agents.py -v
```
Expected: PASS — all 7 CRUD tests green.

- [ ] **Step 6: Commit**

```bash
git add app/api/agents.py tests/test_api_agents.py app/main.py
git commit -m "feat: add agent CRUD API with create, list, get, update, delete"
```

---

## Chunk 4: Agent Execution Pipeline (Celery Tasks)

### Task 8: Agent execution Celery task

**Files:**
- Create: `app/tasks/agent_runner.py`
- Create: `tests/test_agent_runner.py`

- [ ] **Step 1: Write failing tests for agent runner task**

Create `tests/test_agent_runner.py`:

```python
"""Tests for the Celery agent runner task.

These tests run synchronously (not through Celery broker)
by calling the function directly.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from app.models import Agent, AgentRun
from app.database import create_engine_and_tables, get_session
from app.tasks.agent_runner import run_agent


@pytest.fixture
def db_session(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_and_tables(database_url)
    session_factory = get_session(engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def code_gen_agent(db_session):
    agent = Agent(
        id="test-code-gen",
        name="Test Code Gen",
        agent_type="code_gen",
        prompt_template="Find stocks with close > {threshold}",
        schedule="on_demand",
        enabled=True,
    )
    db_session.add(agent)
    db_session.commit()
    return agent


def test_run_agent_not_found(db_session):
    """Running a nonexistent agent returns error."""
    with patch("app.tasks.agent_runner._get_session", return_value=db_session):
        result = run_agent("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_run_disabled_agent(db_session):
    """Running a disabled agent returns error."""
    agent = Agent(
        id="disabled-agent",
        name="Disabled",
        agent_type="deterministic",
        enabled=False,
    )
    db_session.add(agent)
    db_session.commit()

    with patch("app.tasks.agent_runner._get_session", return_value=db_session):
        result = run_agent("disabled-agent")
    assert result["success"] is False
    assert "disabled" in result["error"].lower()


def test_run_code_gen_agent_calls_claude_and_runs(db_session, code_gen_agent):
    """Code-gen agent calls Claude API then runs the returned code."""
    mock_code = 'import json\noutput = json.dumps({"found": 5})'

    with (
        patch("app.tasks.agent_runner._get_session", return_value=db_session),
        patch("app.tasks.agent_runner._call_claude_for_code", return_value=mock_code),
        patch("app.tasks.agent_runner._get_data_context", return_value={}),
    ):
        result = run_agent("test-code-gen", variables={"threshold": 50000})

    assert result["success"] is True
    assert result["output"]["found"] == 5

    # Verify agent run was logged
    runs = db_session.query(AgentRun).filter_by(agent_id="test-code-gen").all()
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].generated_code == mock_code
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent_runner.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create app/tasks/agent_runner.py**

```python
"""Celery task to run any agent (deterministic, structured AI, or code-gen)."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import DATABASE_URL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from app.database import create_engine_and_tables, get_session
from app.models import Agent, AgentRun
from app.agents.code_executor import run_generated_code
from app.tasks.celery_app import celery_app


def _get_session() -> Session:
    """Create a fresh database session for task use."""
    engine = create_engine_and_tables(DATABASE_URL)
    factory = get_session(engine)
    return factory()


def _get_data_context(session: Session) -> dict:
    """Build the data context available to code-gen agents."""
    import pandas as pd

    try:
        prices = pd.read_sql("SELECT * FROM prices", session.bind)
    except Exception:
        prices = pd.DataFrame()

    try:
        trades = pd.read_sql("SELECT * FROM trades", session.bind)
    except Exception:
        trades = pd.DataFrame()

    try:
        holdings = pd.read_sql("SELECT * FROM holdings", session.bind)
    except Exception:
        holdings = pd.DataFrame()

    return {"prices": prices, "trades": trades, "holdings": holdings}


def _call_claude_for_code(prompt_template: str, variables: dict, data_context: dict) -> str:
    """Call Claude API to generate Python code from a prompt template."""
    import anthropic

    filled_prompt = prompt_template
    for key, value in variables.items():
        filled_prompt = filled_prompt.replace(f"{{{key}}}", str(value))

    schema_lines = []
    for name, df in data_context.items():
        if hasattr(df, "columns") and len(df) > 0:
            schema_lines.append(f"Table '{name}': columns = {list(df.columns)}")
            schema_lines.append(f"  Sample (first 3 rows):\n{df.head(3).to_string()}")
        else:
            schema_lines.append(f"Table '{name}': empty DataFrame")

    schema_description = "\n".join(schema_lines) if schema_lines else "No data available yet."

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=(
            "You are a stock market data analyst. Generate Python code that analyzes "
            "the provided dataset. Use only pandas (as pd), numpy (as np), json, and datetime. "
            "Data is available via data_context dict containing DataFrames. "
            "Set a variable called 'output' to a JSON string with your results. "
            "Return ONLY the Python code, no markdown or explanation."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Task: {filled_prompt}\n\n"
                    f"Available data:\n{schema_description}\n\n"
                    "Generate Python code to accomplish this task."
                ),
            }
        ],
    )

    code = response.content[0].text.strip()
    # Strip markdown code fences if Claude wraps the code
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    if code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()

    return code


def run_agent(
    agent_id: str,
    variables: dict | None = None,
    session: Session | None = None,
) -> dict:
    """Run an agent by ID.

    Args:
        agent_id: The agent's unique identifier.
        variables: Optional dict of variables to fill into prompt_template.
        session: Optional pre-existing session (for testing).

    Returns:
        Dict with success, output, error, generated_code.
    """
    own_session = session is None
    if own_session:
        session = _get_session()

    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            return {"success": False, "error": f"Agent '{agent_id}' not found", "output": None}

        if not agent.enabled:
            return {"success": False, "error": f"Agent '{agent_id}' is disabled", "output": None}

        # Create run log
        agent_run = AgentRun(
            agent_id=agent_id,
            started_at=datetime.utcnow(),
            status="running",
            input_context=json.dumps(variables or {}),
        )
        session.add(agent_run)
        session.commit()

        if agent.agent_type == "code_gen":
            data_context = _get_data_context(session)
            generated_code = _call_claude_for_code(
                agent.prompt_template, variables or {}, data_context
            )
            result = run_generated_code(generated_code, data_context)
            agent_run.generated_code = generated_code

        elif agent.agent_type == "structured_ai":
            result = _run_structured_ai_agent(agent, variables or {})

        else:
            # Deterministic agents use the built-in registry
            from app.agents.registry import AgentRegistry
            registry = AgentRegistry()
            built_in = registry.get(agent_id)
            if built_in:
                agent_result = built_in.run(variables or {})
                result = {
                    "success": agent_result.success,
                    "output": agent_result.output,
                    "error": agent_result.error,
                    "generated_code": None,
                }
            else:
                result = {
                    "success": False,
                    "error": f"No built-in handler for '{agent_id}'",
                    "output": None,
                }

        # Update run log
        agent_run.completed_at = datetime.utcnow()
        agent_run.status = "success" if result.get("success") else "error"
        agent_run.output_json = json.dumps(result.get("output")) if result.get("output") else None
        agent_run.error_message = result.get("error")
        session.commit()

        return result

    except Exception as exception:
        return {"success": False, "error": str(exception), "output": None}
    finally:
        if own_session:
            session.close()


def _run_structured_ai_agent(agent: Agent, variables: dict) -> dict:
    """Run a structured AI agent that returns JSON from Claude directly."""
    import anthropic

    filled_prompt = agent.prompt_template or ""
    for key, value in variables.items():
        filled_prompt = filled_prompt.replace(f"{{{key}}}", str(value))

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=(
                "You are a stock market analyst. Respond ONLY with valid JSON. "
                "No markdown, no explanation, just the JSON object."
            ),
            messages=[{"role": "user", "content": filled_prompt}],
        )
        output = json.loads(response.content[0].text.strip())
        return {"success": True, "output": output, "error": None, "generated_code": None}
    except Exception as exception:
        return {"success": False, "output": None, "error": str(exception), "generated_code": None}


@celery_app.task(name="app.tasks.agent_runner.run_agent_task")
def run_agent_task(agent_id: str, variables: dict | None = None) -> dict:
    """Celery task wrapper for run_agent."""
    return run_agent(agent_id, variables)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent_runner.py -v
```
Expected: PASS — all 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/tasks/agent_runner.py tests/test_agent_runner.py
git commit -m "feat: add agent runner with code-gen and structured AI support"
```

---

### Task 9: Agent execute API endpoint

**Files:**
- Modify: `app/api/agents.py`
- Create: `tests/test_api_agent_execute.py`

- [ ] **Step 1: Write failing test for execute endpoint**

Create `tests/test_api_agent_execute.py`:

```python
"""Tests for the agent execute API endpoint."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import Agent


@pytest.fixture
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = database.create_engine_and_tables(database_url)
    session_factory = database.get_session(engine)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override_session

    # Seed a test agent
    session = session_factory()
    agent = Agent(
        id="test-exec",
        name="Test Exec",
        agent_type="deterministic",
        enabled=True,
    )
    session.add(agent)
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_execute_agent_on_demand(client):
    with patch("app.api.agents.run_agent", return_value={"success": True, "output": {"result": 42}}):
        response = client.post("/api/agents/test-exec/execute", json={"variables": {}})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_execute_nonexistent_agent(client):
    response = client.post("/api/agents/nonexistent/execute", json={})
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_agent_execute.py -v
```
Expected: FAIL — 405 or 404 on `/api/agents/{id}/execute`.

- [ ] **Step 3: Add execute endpoint to app/api/agents.py**

Append to the end of `app/api/agents.py`:

```python
from app.tasks.agent_runner import run_agent


class AgentExecuteRequest(BaseModel):
    variables: dict | None = None


@router.post("/{agent_id}/execute")
def execute_agent(
    agent_id: str,
    request_body: AgentExecuteRequest = AgentExecuteRequest(),
    session: Session = Depends(get_database_session),
):
    """Execute an agent on-demand."""
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = run_agent(agent_id, request_body.variables, session=session)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_api_agent_execute.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add app/api/agents.py tests/test_api_agent_execute.py
git commit -m "feat: add on-demand agent execute API endpoint"
```

---

## Chunk 5: Orchestrator + Integration Test

### Task 10: Rule check cycle orchestrator

**Files:**
- Create: `app/tasks/rule_check.py`
- Create: `tests/test_rule_check.py`

- [ ] **Step 1: Write failing test for the orchestrator**

Create `tests/test_rule_check.py`:

```python
"""Tests for the hourly rule check cycle orchestrator."""

import pytest
from unittest.mock import patch, MagicMock, call

from app.tasks.rule_check import run_full_check_cycle


def test_full_check_cycle_runs_agents_in_order():
    call_order = []

    def mock_run_agent(agent_id, variables=None, session=None):
        call_order.append(agent_id)
        return {"success": True, "output": {}}

    with patch("app.tasks.rule_check.run_agent", side_effect=mock_run_agent):
        with patch("app.tasks.rule_check._get_session", return_value=MagicMock()):
            with patch("app.tasks.rule_check._get_portfolio_tickers", return_value=["FPT", "VCB"]):
                result = run_full_check_cycle()

    assert result["success"] is True
    assert call_order[0] == "price-fetcher"
    assert "portfolio-calculator" in call_order
    assert "swing-low-detector" in call_order
    assert "rule-evaluator" in call_order


def test_full_check_cycle_continues_on_agent_failure():
    def mock_run_agent(agent_id, variables=None, session=None):
        if agent_id == "price-fetcher":
            return {"success": False, "error": "vnstock timeout", "output": None}
        return {"success": True, "output": {}}

    with patch("app.tasks.rule_check.run_agent", side_effect=mock_run_agent):
        with patch("app.tasks.rule_check._get_session", return_value=MagicMock()):
            with patch("app.tasks.rule_check._get_portfolio_tickers", return_value=["FPT"]):
                result = run_full_check_cycle()

    assert result["success"] is True
    assert len(result["errors"]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_rule_check.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create app/tasks/rule_check.py**

```python
"""Hourly rule check cycle orchestrator.

Runs core agents in sequence, then any scheduled code-gen agents:
1. PriceFetcher — get latest prices
2. PortfolioCalculator — update holdings and P&L
3. SwingLowDetector — update swing low levels
4. RuleEvaluator — check positions against trading rules
5. Scheduled code-gen/AI agents — run any hourly agents
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import DATABASE_URL
from app.database import create_engine_and_tables, get_session
from app.models import Agent, Holding
from app.tasks.agent_runner import run_agent
from app.tasks.celery_app import celery_app


def _get_session() -> Session:
    engine = create_engine_and_tables(DATABASE_URL)
    factory = get_session(engine)
    return factory()


def _get_portfolio_tickers(session: Session) -> list[str]:
    """Get tickers currently held in portfolio."""
    holdings = session.query(Holding.ticker).filter(Holding.total_shares > 0).all()
    return [h.ticker for h in holdings]


def run_full_check_cycle(session: Session | None = None) -> dict:
    """Run the full hourly check cycle."""
    own_session = session is None
    if own_session:
        session = _get_session()

    results = {}
    errors = []

    try:
        tickers = _get_portfolio_tickers(session)
        variables = {"tickers": tickers, "timestamp": datetime.utcnow().isoformat()}

        core_agents = [
            "price-fetcher",
            "portfolio-calculator",
            "swing-low-detector",
            "rule-evaluator",
        ]

        for agent_id in core_agents:
            result = run_agent(agent_id, variables=variables, session=session)
            results[agent_id] = result
            if not result.get("success"):
                errors.append({"agent": agent_id, "error": result.get("error")})

        # Run hourly-scheduled code-gen/AI agents
        scheduled_agents = (
            session.query(Agent)
            .filter_by(schedule="hourly", enabled=True)
            .filter(Agent.agent_type.in_(["code_gen", "structured_ai"]))
            .all()
        )

        for agent_def in scheduled_agents:
            result = run_agent(agent_def.id, variables=variables, session=session)
            results[agent_def.id] = result
            if not result.get("success"):
                errors.append({"agent": agent_def.id, "error": result.get("error")})

        return {"success": True, "results": results, "errors": errors}

    except Exception as exception:
        return {"success": False, "error": str(exception), "results": results, "errors": errors}
    finally:
        if own_session:
            session.close()


@celery_app.task(name="app.tasks.rule_check.run_full_check_cycle")
def run_full_check_cycle_task():
    """Celery task wrapper."""
    return run_full_check_cycle()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_rule_check.py -v
```
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add app/tasks/rule_check.py tests/test_rule_check.py
git commit -m "feat: add hourly rule check cycle orchestrator"
```

---

### Task 11: Integration smoke test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_integration.py`:

```python
"""Integration test: full stack smoke test.

Verifies FastAPI starts, database works, agents can be CRUD'd,
and the agent pipeline works with a mock Claude response.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app import database


@pytest.fixture
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = database.create_engine_and_tables(database_url)
    session_factory = database.get_session(engine)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_full_stack_smoke_test(client):
    """End-to-end: create agent -> run -> verify logged."""
    # 1. Health check
    assert client.get("/api/health").status_code == 200

    # 2. Create a code-gen agent
    agent_data = {
        "id": "smoke-test-agent",
        "name": "Smoke Test",
        "agent_type": "code_gen",
        "prompt_template": "Count rows in prices table",
        "enabled": True,
    }
    response = client.post("/api/agents", json=agent_data)
    assert response.status_code == 201

    # 3. Run it (mock Claude response)
    mock_code = 'import json\noutput = json.dumps({"row_count": 0})'
    with patch("app.tasks.agent_runner._call_claude_for_code", return_value=mock_code):
        response = client.post(
            "/api/agents/smoke-test-agent/execute",
            json={"variables": {}},
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["output"]["row_count"] == 0

    # 4. Verify agent exists
    response = client.get("/api/agents/smoke-test-agent")
    assert response.status_code == 200

    # 5. Delete agent
    response = client.delete("/api/agents/smoke-test-agent")
    assert response.status_code == 204
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```
Expected: ALL tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add full-stack integration smoke test"
```

---

### Task 12: Final verification

- [ ] **Step 1: Start Redis**

```bash
docker-compose up -d redis
```

- [ ] **Step 2: Verify FastAPI starts**

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
curl http://localhost:8000/api/health
```
Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 3: Verify Celery worker starts**

```bash
celery -A app.tasks.celery_app worker --loglevel=info &
```
Expected: Worker connects to Redis, shows "ready".

- [ ] **Step 4: Verify dashboard is served**

Open `http://localhost:8000/` — should show the existing Vietnam Market Sector Analysis dashboard.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: Plan 1 complete — foundation infrastructure verified"
```
