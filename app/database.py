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
