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

if DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
