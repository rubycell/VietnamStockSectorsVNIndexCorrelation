# Plan 1: Foundation — FastAPI + SQLite + Agent Framework + OpenClaw + Docker

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational infrastructure — Dockerized FastAPI server with SQLite database, agent base framework, OpenClaw gateway with skills and cron scheduling, and a full Docker Compose test suite.

**Architecture:** FastAPI serves the API and static dashboard. OpenClaw handles messaging (Telegram/WhatsApp), scheduling (cron), and agent orchestration by calling FastAPI endpoints via Docker network. SQLite stores all persistent state. Every feature is an "agent" — either deterministic or AI-powered code-gen.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, SQLAlchemy, SQLite, anthropic SDK, httpx, pandas, openpyxl, vnstock, OpenClaw, Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-10-portfolio-trading-system-design.md`

---

## Chunk 1: Project Scaffolding + Docker + Database

### Task 1: Create project structure, dependencies, and Dockerfile

**Files:**
- Modify: `requirements.txt`
- Create: `app/__init__.py` (and subpackages)
- Create: `app/config.py`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Update requirements.txt**

```
vnstock
pandas
numpy
pytz
openpyxl
fastapi
uvicorn[standard]
sqlalchemy
python-multipart
anthropic
httpx
pytest
pytest-asyncio
```

- [ ] **Step 2: Create app package directories**

```bash
mkdir -p app/api app/pipeline app/engine app/agents tests openclaw/skills
touch app/__init__.py app/api/__init__.py app/pipeline/__init__.py app/engine/__init__.py app/agents/__init__.py tests/__init__.py
```

- [ ] **Step 3: Create app/config.py**

```python
"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'portfolio.db'}")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

VNSTOCK_SOURCE = os.getenv("VNSTOCK_SOURCE", "VCI")
MARKET_OPEN_HOUR = int(os.getenv("MARKET_OPEN_HOUR", "9"))
MARKET_CLOSE_HOUR = int(os.getenv("MARKET_CLOSE_HOUR", "15"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DATA_DIR = PROJECT_ROOT / "data"
```

- [ ] **Step 4: Create .env.example**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 5: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY dashboard/ dashboard/
COPY data/ data/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6: Create docker-compose.yml**

```yaml
version: "3.8"

services:
  fastapi:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./dashboard:/app/dashboard
    env_file: .env
    environment:
      - DATABASE_URL=sqlite:///data/portfolio.db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - app-net

  openclaw:
    image: ghcr.io/openclaw/openclaw:latest
    volumes:
      - ./openclaw:/home/node/.openclaw
    ports:
      - "18789:18789"
    environment:
      - HOME=/home/node
    command: ["node", "dist/index.js", "gateway", "--bind", "lan"]
    depends_on:
      fastapi:
        condition: service_healthy
    networks:
      - app-net

networks:
  app-net:
```

- [ ] **Step 7: Create docker-compose.test.yml**

```yaml
version: "3.8"

services:
  test-runner:
    build: .
    command: pytest tests/ -v --tb=short
    volumes:
      - ./app:/app/app
      - ./tests:/app/tests
      - ./dashboard:/app/dashboard
    environment:
      - DATABASE_URL=sqlite:////tmp/test.db
      - ANTHROPIC_API_KEY=test-key
    networks:
      - test-net

networks:
  test-net:
```

- [ ] **Step 8: Install dependencies locally and verify**

```bash
source venv/bin/activate
pip install -r requirements.txt
python -c "import fastapi, sqlalchemy, anthropic, httpx; print('All imports OK')"
```

- [ ] **Step 9: Commit**

```bash
git add requirements.txt Dockerfile docker-compose.yml docker-compose.test.yml .env.example app/ tests/ openclaw/
git commit -m "chore: scaffold project with Docker, FastAPI, and OpenClaw structure"
```

---

### Task 2: SQLite database models

**Files:**
- Create: `app/database.py`
- Create: `app/models.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing test for database setup**

Create `tests/test_database.py`:

```python
"""Tests for database setup and model creation."""

import pytest
from sqlalchemy import inspect, text
from app.database import create_engine_and_tables, get_session


def test_create_engine_and_tables_creates_all_tables(tmp_path):
    """All expected tables exist after initialization."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_and_tables(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "trade_fills", "trades", "holdings", "prices",
        "swing_lows", "price_levels", "alerts", "config",
        "agents", "agent_runs", "import_batches",
    }
    assert expected_tables.issubset(table_names), f"Missing: {expected_tables - table_names}"


def test_get_session_returns_usable_session(tmp_path):
    """Session can query the database."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_and_tables(database_url)
    session_factory = get_session(engine)
    with session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar()
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
    __table_args__ = (
        UniqueConstraint("order_no", "matched_price", "matched_volume", "trading_date", name="unique_fill"),
    )


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
    vwap_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    current_price = Column(Float, nullable=True)
    position_number = Column(Integer, default=1)
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
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_database.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/database.py app/models.py tests/test_database.py
git commit -m "feat: add SQLite database models for all 11 system tables"
```

---

## Chunk 2: Agent Base Framework

### Task 3: Agent base class and registry

**Files:**
- Create: `app/agents/base.py`
- Create: `app/agents/registry.py`
- Create: `tests/test_agents_base.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_agents_base.py`:

```python
"""Tests for agent base class and registry."""

from app.agents.base import BaseAgent, AgentResult
from app.agents.registry import AgentRegistry


class FakeAgent(BaseAgent):
    agent_id = "fake-agent"
    agent_type = "deterministic"

    def run(self, context: dict) -> AgentResult:
        return AgentResult(success=True, output={"message": f"processed {context.get('ticker', '?')}"})


def test_base_agent_run_returns_result():
    result = FakeAgent().run({"ticker": "FPT"})
    assert result.success is True
    assert result.output["message"] == "processed FPT"


def test_agent_result_error_case():
    result = AgentResult(success=False, error="broke")
    assert result.success is False
    assert result.output is None


def test_registry_register_and_get():
    registry = AgentRegistry()
    registry.register(FakeAgent)
    assert isinstance(registry.get("fake-agent"), FakeAgent)


def test_registry_get_unknown_returns_none():
    assert AgentRegistry().get("nope") is None


def test_registry_list_agents():
    registry = AgentRegistry()
    registry.register(FakeAgent)
    agents = registry.list_agents()
    assert agents == [{"id": "fake-agent", "type": "deterministic"}]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agents_base.py -v
```

- [ ] **Step 3: Create app/agents/base.py**

```python
"""Base class for all agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResult:
    success: bool
    output: dict[str, Any] | None = None
    error: str | None = None
    generated_code: str | None = None


class BaseAgent(ABC):
    agent_id: str = ""
    agent_type: str = "deterministic"

    @abstractmethod
    def run(self, context: dict) -> AgentResult:
        ...
```

- [ ] **Step 4: Create app/agents/registry.py**

```python
"""Agent registry — maps agent IDs to agent classes."""

from typing import Type
from app.agents.base import BaseAgent


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Type[BaseAgent]] = {}

    def register(self, agent_class: Type[BaseAgent]) -> None:
        self._agents[agent_class.agent_id] = agent_class

    def get(self, agent_id: str) -> BaseAgent | None:
        cls = self._agents.get(agent_id)
        return cls() if cls else None

    def list_agents(self) -> list[dict]:
        return [{"id": c.agent_id, "type": c.agent_type} for c in self._agents.values()]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_agents_base.py -v
```

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

**Note:** Uses `exec()` intentionally — the entire app runs in Docker (user-approved).

- [ ] **Step 1: Write failing tests**

Create `tests/test_code_executor.py`:

```python
"""Tests for the code runner used by code-gen agents."""

import pandas as pd
from app.agents.code_executor import run_generated_code


def test_simple_code():
    code = 'import json\noutput = json.dumps({"total": 42})'
    result = run_generated_code(code, {})
    assert result["success"] is True
    assert result["output"] == {"total": 42}


def test_code_with_data_context():
    code = """
import json, pandas as pd
df = data_context["prices"]
output = json.dumps({"avg": round(df["close"].mean(), 2)})
"""
    prices = pd.DataFrame({"close": [100.0, 110.0, 105.0]})
    result = run_generated_code(code, {"prices": prices})
    assert result["output"]["avg"] == 105.0


def test_syntax_error():
    result = run_generated_code("def broken(:", {})
    assert result["success"] is False
    assert "SyntaxError" in result["error"] or "invalid syntax" in result["error"]


def test_runtime_error():
    code = 'import json\nx = 1/0\noutput = json.dumps({})'
    result = run_generated_code(code, {})
    assert result["success"] is False
    assert "ZeroDivisionError" in result["error"]


def test_captures_generated_code():
    code = 'import json\noutput = json.dumps({"ok": True})'
    assert run_generated_code(code, {})["generated_code"] == code
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_code_executor.py -v
```

- [ ] **Step 3: Create app/agents/code_executor.py**

```python
"""Run Python code generated by AI agents.

SECURITY: Uses exec() intentionally. Runs inside Docker container (approved design).
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

    Code must set 'output' variable to a JSON string.
    """
    namespace = {
        "pd": pandas, "pandas": pandas,
        "np": numpy, "numpy": numpy,
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
        exec(compiled, namespace)  # noqa: S102
        signal.alarm(0)

        raw_output = namespace.get("output")
        if raw_output is None:
            return {"success": False, "output": None, "error": "No 'output' variable set", "generated_code": code}

        parsed = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
        return {"success": True, "output": parsed, "error": None, "generated_code": code}

    except (TimeoutError, Exception) as err:
        signal.alarm(0)
        error_msg = str(err) if isinstance(err, TimeoutError) else traceback.format_exc()
        return {"success": False, "output": None, "error": error_msg, "generated_code": code}
    finally:
        signal.signal(signal.SIGALRM, previous_handler)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_code_executor.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/agents/code_executor.py tests/test_code_executor.py
git commit -m "feat: add code runner for AI-generated agent code"
```

---

## Chunk 3: FastAPI Server + Agent API

### Task 5: FastAPI entry point

**Files:**
- Create: `app/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_main.py`:

```python
"""Tests for FastAPI application."""

from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_served():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py -v
```

- [ ] **Step 3: Create app/main.py**

```python
"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import DASHBOARD_DIR, DATABASE_URL
from app.database import create_engine_and_tables, get_session

app = FastAPI(title="Portfolio Trading System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine_and_tables(DATABASE_URL)
SessionFactory = get_session(engine)


def get_database_session():
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": app.version}


# Import and register routers here (before static mount)
# from app.api.agents import router as agents_router
# app.include_router(agents_router)

if DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_main.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: add FastAPI entry point with health check and dashboard"
```

---

### Task 6: Agent CRUD API

**Files:**
- Create: `app/api/agents.py`
- Create: `tests/test_api_agents.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api_agents.py`:

```python
"""Tests for agent management API."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import database


@pytest.fixture
def client(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = database.create_engine_and_tables(db_url)
    factory = database.get_session(engine)

    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


SAMPLE = {
    "id": "test-agent", "name": "Test", "agent_type": "code_gen",
    "prompt_template": "Analyze {ticker}", "enabled": True,
}


def test_create_agent(client):
    r = client.post("/api/agents", json=SAMPLE)
    assert r.status_code == 201
    assert r.json()["id"] == "test-agent"


def test_list_agents(client):
    client.post("/api/agents", json=SAMPLE)
    assert len(client.get("/api/agents").json()) == 1


def test_get_agent(client):
    client.post("/api/agents", json=SAMPLE)
    assert client.get("/api/agents/test-agent").status_code == 200


def test_get_not_found(client):
    assert client.get("/api/agents/nope").status_code == 404


def test_update_agent(client):
    client.post("/api/agents", json=SAMPLE)
    r = client.put("/api/agents/test-agent", json={"name": "Updated", "enabled": False})
    assert r.json()["name"] == "Updated"
    assert r.json()["enabled"] is False


def test_delete_agent(client):
    client.post("/api/agents", json=SAMPLE)
    assert client.delete("/api/agents/test-agent").status_code == 204
    assert client.get("/api/agents/test-agent").status_code == 404


def test_duplicate_fails(client):
    client.post("/api/agents", json=SAMPLE)
    assert client.post("/api/agents", json=SAMPLE).status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_agents.py -v
```

- [ ] **Step 3: Create app/api/agents.py**

```python
"""Agent management CRUD + execute API."""

import json
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
def create_agent(data: AgentCreate, session: Session = Depends(get_database_session)):
    if session.query(Agent).filter_by(id=data.id).first():
        raise HTTPException(409, "Agent already exists")
    agent = Agent(**data.model_dump())
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
        raise HTTPException(404, "Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, data: AgentUpdate, session: Session = Depends(get_database_session)):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    agent.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: str, session: Session = Depends(get_database_session)):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    session.delete(agent)
    session.commit()
```

- [ ] **Step 4: Register router in app/main.py**

Uncomment and update the router registration in `app/main.py` (before static mount):

```python
from app.api.agents import router as agents_router

app.include_router(agents_router)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_api_agents.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/api/agents.py tests/test_api_agents.py app/main.py
git commit -m "feat: add agent CRUD API"
```

---

## Chunk 4: Agent Execution + Check Cycle API

### Task 7: Agent runner (execute code-gen and structured AI agents)

**Files:**
- Create: `app/agents/runner.py`
- Create: `tests/test_agent_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_agent_runner.py`:

```python
"""Tests for the agent runner."""

import pytest
from unittest.mock import patch
from app.models import Agent, AgentRun
from app.database import create_engine_and_tables, get_session
from app.agents.runner import run_agent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = get_session(engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def code_gen_agent(db_session):
    agent = Agent(id="test-cg", name="Test CG", agent_type="code_gen",
                  prompt_template="Find stocks > {threshold}", enabled=True)
    db_session.add(agent)
    db_session.commit()
    return agent


def test_agent_not_found(db_session):
    result = run_agent("nope", session=db_session)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_disabled_agent(db_session):
    db_session.add(Agent(id="off", name="Off", agent_type="deterministic", enabled=False))
    db_session.commit()
    result = run_agent("off", session=db_session)
    assert "disabled" in result["error"].lower()


def test_code_gen_agent(db_session, code_gen_agent):
    mock_code = 'import json\noutput = json.dumps({"found": 5})'
    with (
        patch("app.agents.runner._call_claude_for_code", return_value=mock_code),
        patch("app.agents.runner._get_data_context", return_value={}),
    ):
        result = run_agent("test-cg", variables={"threshold": 50000}, session=db_session)
    assert result["success"] is True
    assert result["output"]["found"] == 5
    runs = db_session.query(AgentRun).filter_by(agent_id="test-cg").all()
    assert len(runs) == 1
    assert runs[0].status == "success"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent_runner.py -v
```

- [ ] **Step 3: Create app/agents/runner.py**

```python
"""Agent runner — executes any agent type."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from app.models import Agent, AgentRun
from app.agents.code_executor import run_generated_code
from app.agents.registry import AgentRegistry


def _get_data_context(session: Session) -> dict:
    """Build data context for code-gen agents."""
    import pandas as pd
    tables = {"prices": "prices", "trades": "trades", "holdings": "holdings"}
    context = {}
    for key, table in tables.items():
        try:
            context[key] = pd.read_sql(f"SELECT * FROM {table}", session.bind)
        except Exception:
            context[key] = pd.DataFrame()
    return context


def _call_claude_for_code(prompt_template: str, variables: dict, data_context: dict) -> str:
    """Call Claude API to generate Python analysis code."""
    import anthropic

    filled = prompt_template
    for k, v in variables.items():
        filled = filled.replace(f"{{{k}}}", str(v))

    schema_lines = []
    for name, df in data_context.items():
        if hasattr(df, "columns") and len(df) > 0:
            schema_lines.append(f"Table '{name}': columns = {list(df.columns)}")
            schema_lines.append(f"  Sample:\n{df.head(3).to_string()}")
        else:
            schema_lines.append(f"Table '{name}': empty")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=(
            "You are a stock market data analyst. Generate Python code using pandas/numpy. "
            "Data is in data_context dict. Set 'output' to a JSON string. "
            "Return ONLY Python code, no markdown."
        ),
        messages=[{"role": "user", "content": f"Task: {filled}\n\nData:\n{chr(10).join(schema_lines)}"}],
    )

    code = response.content[0].text.strip()
    for fence in ["```python", "```"]:
        if code.startswith(fence):
            code = code[len(fence):].strip()
    if code.endswith("```"):
        code = code[:-3].strip()
    return code


def run_agent(agent_id: str, variables: dict | None = None, session: Session | None = None) -> dict:
    """Execute an agent by ID. Returns dict with success, output, error."""
    if session is None:
        raise ValueError("Session required")

    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        return {"success": False, "error": f"Agent '{agent_id}' not found", "output": None}
    if not agent.enabled:
        return {"success": False, "error": f"Agent '{agent_id}' is disabled", "output": None}

    agent_run = AgentRun(agent_id=agent_id, started_at=datetime.utcnow(), status="running",
                         input_context=json.dumps(variables or {}))
    session.add(agent_run)
    session.commit()

    try:
        if agent.agent_type == "code_gen":
            data_context = _get_data_context(session)
            generated_code = _call_claude_for_code(agent.prompt_template, variables or {}, data_context)
            result = run_generated_code(generated_code, data_context)
            agent_run.generated_code = generated_code

        elif agent.agent_type == "structured_ai":
            result = _run_structured_ai(agent, variables or {})

        else:
            built_in = AgentRegistry().get(agent_id)
            if built_in:
                r = built_in.run(variables or {})
                result = {"success": r.success, "output": r.output, "error": r.error, "generated_code": None}
            else:
                result = {"success": False, "error": f"No handler for '{agent_id}'", "output": None}

        agent_run.completed_at = datetime.utcnow()
        agent_run.status = "success" if result.get("success") else "error"
        agent_run.output_json = json.dumps(result.get("output")) if result.get("output") else None
        agent_run.error_message = result.get("error")
        session.commit()
        return result

    except Exception as err:
        agent_run.completed_at = datetime.utcnow()
        agent_run.status = "error"
        agent_run.error_message = str(err)
        session.commit()
        return {"success": False, "error": str(err), "output": None}


def _run_structured_ai(agent: Agent, variables: dict) -> dict:
    """Structured AI agent: Claude returns JSON directly."""
    import anthropic

    filled = agent.prompt_template or ""
    for k, v in variables.items():
        filled = filled.replace(f"{{{k}}}", str(v))

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=1024,
            system="Respond ONLY with valid JSON. No markdown.",
            messages=[{"role": "user", "content": filled}],
        )
        return {"success": True, "output": json.loads(response.content[0].text.strip()),
                "error": None, "generated_code": None}
    except Exception as err:
        return {"success": False, "output": None, "error": str(err), "generated_code": None}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent_runner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/agents/runner.py tests/test_agent_runner.py
git commit -m "feat: add agent runner with code-gen and structured AI support"
```

---

### Task 8: Agent execute + check-cycle API endpoints

**Files:**
- Modify: `app/api/agents.py`
- Create: `app/api/check_cycle.py`
- Create: `tests/test_api_check_cycle.py`

- [ ] **Step 1: Add execute endpoint to app/api/agents.py**

Append to `app/api/agents.py`:

```python
from app.agents.runner import run_agent


class AgentExecuteRequest(BaseModel):
    variables: dict | None = None


@router.post("/{agent_id}/execute")
def execute_agent(agent_id: str, body: AgentExecuteRequest = AgentExecuteRequest(),
                  session: Session = Depends(get_database_session)):
    agent = session.query(Agent).filter_by(id=agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return run_agent(agent_id, body.variables, session=session)
```

- [ ] **Step 2: Create app/api/check_cycle.py**

```python
"""Full check cycle endpoint — called by OpenClaw cron."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Agent, Holding
from app.agents.runner import run_agent

router = APIRouter(tags=["check-cycle"])


@router.post("/api/check-cycle")
def run_check_cycle(session: Session = Depends(get_database_session)):
    """Run the full hourly check: prices → portfolio → swing lows → rules → scheduled agents."""
    tickers = [h.ticker for h in session.query(Holding.ticker).filter(Holding.total_shares > 0).all()]
    variables = {"tickers": tickers, "timestamp": datetime.utcnow().isoformat()}

    results = {}
    errors = []

    for agent_id in ["price-fetcher", "portfolio-calculator", "swing-low-detector", "rule-evaluator"]:
        result = run_agent(agent_id, variables=variables, session=session)
        results[agent_id] = result
        if not result.get("success"):
            errors.append({"agent": agent_id, "error": result.get("error")})

    scheduled = (
        session.query(Agent)
        .filter_by(schedule="hourly", enabled=True)
        .filter(Agent.agent_type.in_(["code_gen", "structured_ai"]))
        .all()
    )
    for agent_def in scheduled:
        result = run_agent(agent_def.id, variables=variables, session=session)
        results[agent_def.id] = result
        if not result.get("success"):
            errors.append({"agent": agent_def.id, "error": result.get("error")})

    return {"success": True, "results": results, "errors": errors}
```

- [ ] **Step 3: Register check-cycle router in app/main.py**

Add before the static mount:

```python
from app.api.check_cycle import router as check_cycle_router

app.include_router(check_cycle_router)
```

- [ ] **Step 4: Write test for check cycle**

Create `tests/test_api_check_cycle.py`:

```python
"""Tests for the check-cycle endpoint."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app import database


def test_check_cycle_returns_results(tmp_path):
    engine = database.create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = database.get_session(engine)

    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override
    client = TestClient(app)

    with patch("app.api.check_cycle.run_agent", return_value={"success": True, "output": {}}):
        response = client.post("/api/check-cycle")

    assert response.status_code == 200
    assert response.json()["success"] is True
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_api_check_cycle.py tests/test_api_agents.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/api/agents.py app/api/check_cycle.py app/main.py tests/test_api_check_cycle.py
git commit -m "feat: add agent execute and check-cycle API endpoints"
```

---

## Chunk 5: OpenClaw Skills + Docker Integration Tests

### Task 9: Create OpenClaw skills

**Files:**
- Create: `openclaw/openclaw.json`
- Create: `openclaw/skills/full-check-cycle/SKILL.md`
- Create: `openclaw/skills/check-portfolio/SKILL.md`
- Create: `openclaw/skills/run-agent/SKILL.md`

- [ ] **Step 1: Create openclaw/openclaw.json**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "${TELEGRAM_BOT_TOKEN}",
      "dmPolicy": "pairing"
    }
  },
  "skills": {
    "entries": {
      "full-check-cycle": {
        "enabled": true,
        "env": {
          "FASTAPI_URL": "http://fastapi:8000"
        }
      },
      "check-portfolio": {
        "enabled": true,
        "env": {
          "FASTAPI_URL": "http://fastapi:8000"
        }
      },
      "run-agent": {
        "enabled": true,
        "env": {
          "FASTAPI_URL": "http://fastapi:8000"
        }
      }
    }
  }
}
```

- [ ] **Step 2: Create full-check-cycle skill**

Create `openclaw/skills/full-check-cycle/SKILL.md`:

```markdown
---
name: full-check-cycle
description: Run the complete trading check cycle — fetch prices, update portfolio, detect swing lows, evaluate rules, and run scheduled agents
---

## Instructions

When asked to run a check cycle, market check, or hourly check:

1. Call the FastAPI backend:
   ```
   curl -X POST {env:FASTAPI_URL}/api/check-cycle
   ```

2. Parse the JSON response. It contains:
   - `success`: whether the cycle completed
   - `results`: per-agent results
   - `errors`: any agent failures

3. Summarize the results for the user:
   - List any triggered trading rules with their alert messages
   - Report any agent errors
   - If no rules triggered, say "All clear — no rules triggered this cycle"

4. If critical alerts exist (rules #4 or #9), format them prominently.
```

- [ ] **Step 3: Create check-portfolio skill**

Create `openclaw/skills/check-portfolio/SKILL.md`:

```markdown
---
name: check-portfolio
description: Check current portfolio holdings, P&L, and position status
---

## Instructions

When asked about portfolio, holdings, positions, or P&L:

1. Call: `curl {env:FASTAPI_URL}/api/portfolio`

2. Format the response as a clear summary:
   - Total portfolio value and overall P&L
   - Per-ticker: shares held, average cost, current price, unrealized P&L %
   - Highlight any positions with > 10% loss

3. If asked about a specific ticker, filter to just that ticker.
```

- [ ] **Step 4: Create run-agent skill**

Create `openclaw/skills/run-agent/SKILL.md`:

```markdown
---
name: run-agent
description: Run a specific AI agent by name or ID
---

## Instructions

When asked to run an agent (e.g., "run the trendy sector detector", "check unusual volume"):

1. First, list available agents: `curl {env:FASTAPI_URL}/api/agents`
2. Find the matching agent by name or ID
3. Execute it: `curl -X POST {env:FASTAPI_URL}/api/agents/{agent_id}/execute -H "Content-Type: application/json" -d '{"variables": {}}'`
4. Present the results clearly. If the agent found insights, highlight them.
5. If the agent failed, report the error.
```

- [ ] **Step 5: Commit**

```bash
git add openclaw/
git commit -m "feat: add OpenClaw config and skills for portfolio, check cycle, run agent"
```

---

### Task 10: Integration smoke test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_integration.py`:

```python
"""Integration smoke test: full API flow."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app import database


@pytest.fixture
def client(tmp_path):
    engine = database.create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = database.get_session(engine)

    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_full_stack(client):
    # Health
    assert client.get("/api/health").json()["status"] == "ok"

    # Create agent
    r = client.post("/api/agents", json={
        "id": "smoke", "name": "Smoke", "agent_type": "code_gen",
        "prompt_template": "Count prices", "enabled": True,
    })
    assert r.status_code == 201

    # Execute with mocked Claude
    mock_code = 'import json\noutput = json.dumps({"count": 0})'
    with patch("app.agents.runner._call_claude_for_code", return_value=mock_code):
        r = client.post("/api/agents/smoke/execute", json={"variables": {}})
    assert r.json()["success"] is True
    assert r.json()["output"]["count"] == 0

    # Check cycle with mocked agent runner
    with patch("app.api.check_cycle.run_agent", return_value={"success": True, "output": {}}):
        r = client.post("/api/check-cycle")
    assert r.json()["success"] is True

    # Cleanup
    assert client.delete("/api/agents/smoke").status_code == 204
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

### Task 11: Docker build and verify

- [ ] **Step 1: Build and start Docker Compose**

```bash
docker-compose build fastapi
docker-compose up -d fastapi
```

- [ ] **Step 2: Verify health check**

```bash
curl http://localhost:8000/api/health
```
Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 3: Verify dashboard**

```bash
curl -s http://localhost:8000/ | head -5
```
Expected: HTML content with "Vietnam"

- [ ] **Step 4: Run tests in Docker**

```bash
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```
Expected: All tests pass inside the container.

- [ ] **Step 5: Verify agent API works in Docker**

```bash
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"id": "docker-test", "name": "Docker Test", "agent_type": "code_gen", "enabled": true}'

curl http://localhost:8000/api/agents

curl -X DELETE http://localhost:8000/api/agents/docker-test
```

- [ ] **Step 6: Stop and commit**

```bash
docker-compose down
git add -A
git commit -m "chore: Plan 1 complete — foundation with Docker verified"
```
