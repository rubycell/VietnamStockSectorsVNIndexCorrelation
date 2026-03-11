"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import DASHBOARD_DIR, DATABASE_URL
from app.database import create_engine_and_tables, get_session
from app.agents.seed import seed_agents

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


@app.on_event("startup")
def startup_event():
    """Seed initial agent definitions and default config on application start."""
    from app.models import Config as ConfigModel

    session = SessionFactory()
    try:
        seed_agents(session)

        # Seed default config values if not already set
        defaults = {
            "round_number_increments": {
                "value": "10,50",
                "description": "Round number increments in x1000 VND (e.g. 10=10k, 50=50k, 100=100k)",
            },
        }
        for key, entry in defaults.items():
            if not session.query(ConfigModel).filter_by(key=key).first():
                session.add(ConfigModel(key=key, value=entry["value"], description=entry["description"]))
        session.commit()
    finally:
        session.close()


def get_database_session():
    """Yield a database session and ensure it is closed after use."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@app.get("/api/health")
def health_check():
    """Return application health status."""
    return {"status": "ok", "version": app.version}


# Import and register routers here (before static mount)
from app.api.agents import router as agents_router
app.include_router(agents_router)

from app.api.check_cycle import router as check_cycle_router
app.include_router(check_cycle_router)

from app.api.portfolio import router as portfolio_router
app.include_router(portfolio_router)

from app.api.upload import router as upload_router
app.include_router(upload_router)

from app.api.prices import router as prices_router
app.include_router(prices_router)

from app.api.swing_lows import router as swing_lows_router
app.include_router(swing_lows_router)

from app.api.config_api import router as config_router
app.include_router(config_router)

from app.api.rules import router as rules_router
app.include_router(rules_router)

from app.api.alerts import router as alerts_router
app.include_router(alerts_router)

from app.api.reports import router as reports_router
app.include_router(reports_router)

from app.api.analyze_report import router as analyze_router
app.include_router(analyze_router)

from app.api.jobs import router as jobs_router
app.include_router(jobs_router)

from app.api.artifacts import router as artifacts_router
app.include_router(artifacts_router)

from app.api.levels import router as levels_router
app.include_router(levels_router)

from app.api.positions import router as positions_router
app.include_router(positions_router)

from app.api.trades import router as trades_router
app.include_router(trades_router)

from app.api.import_snapshot import router as import_snapshot_router
app.include_router(import_snapshot_router)

if DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
